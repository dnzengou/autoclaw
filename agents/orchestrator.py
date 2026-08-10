#!/usr/bin/env python3
"""agents/orchestrator.py — plan / validate / approve / execute / audit.

The orchestrator receives a natural-language request, picks the right sub-agent
(research | ops | free-form), lets the LLM propose a tool + args, checks against
policies.yaml, prompts the user if the tool is in the "approval" bucket, runs
the tool, and appends an audit record. Every step is logged.

Usage:
    python agents/orchestrator.py research "What were the Q3 findings?"
    python agents/orchestrator.py ops     "Summarize my inbox and draft replies to Alice"
    python agents/orchestrator.py chat    "Hello, what's on my plate today?"
    python agents/orchestrator.py --auto-approve ops "..."        # skip prompts (dangerous)
    python agents/orchestrator.py list-tools

Env:
    BITNET_URL              LLM endpoint (default http://localhost:8081/v1)
    AUTOCLAW_POLICIES       path to policies.yaml
    AUTOCLAW_AUDIT_LOG      path to audit sink (default ~/.autoclaw/audit.jsonl)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents import audit, tools  # noqa: E402
from agents.research_agent import research  # noqa: E402
from agents.ops_agent import ops  # noqa: E402
from memory.manager import Memory  # noqa: E402

BITNET_URL = os.environ.get("BITNET_URL", "http://localhost:8081/v1")
POLICIES_PATH = Path(os.environ.get("AUTOCLAW_POLICIES",
                                     Path(__file__).parent / "policies.yaml"))


# ─── policies ──────────────────────────────────────────────────────────────

def _strip_comment(s: str) -> str:
    """Strip a trailing YAML comment from a value line, respecting simple quoting."""
    in_dq = False
    for i, ch in enumerate(s):
        if ch == '"':
            in_dq = not in_dq
        elif ch == "#" and not in_dq and (i == 0 or s[i - 1].isspace()):
            return s[:i].rstrip()
    return s.rstrip()


def _yaml_unescape(s: str) -> str:
    """Apply the minimal YAML double-quoted escape sequences we use in policies.yaml."""
    return (s.replace('\\\\', '\x00')  # protect literal backslashes
             .replace('\\n', '\n')
             .replace('\\t', '\t')
             .replace('\\"', '"')
             .replace('\x00', '\\'))


def _load_policies() -> dict:
    """Load policies.yaml. Minimal stdlib parser (no pyyaml dep).

    Grammar handled:
      key: value                    (top-level scalars; # comments stripped)
      key:                          (top-level section — list or map)
        - item                      (list under top-level)
        subkey:                     (nested map under top-level, e.g. 'constraints:')
          leaf:                     (nested list header inside map)
            - item                  (list items)
    """
    text = POLICIES_PATH.read_text(encoding="utf-8")
    result: dict = {"auto": [], "approval": [], "deny": [], "constraints": {}, "default": "approval"}
    top_key = None           # e.g. 'auto', 'approval', 'constraints'
    nested_key = None        # under constraints: e.g. 'web.fetch'
    leaf_key = None          # under constraints.<nested>: e.g. 'url_deny_patterns'

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if indent == 0:
            if stripped.endswith(":"):
                top_key = stripped[:-1].strip()
                nested_key = leaf_key = None
            elif ":" in stripped:
                k, v = stripped.split(":", 1)
                result[k.strip()] = _strip_comment(v.strip())
                top_key = nested_key = leaf_key = None
            continue

        if indent == 2:
            if stripped.startswith("- "):
                result.setdefault(top_key, []).append(_strip_comment(stripped[2:].strip()))
            elif stripped.endswith(":"):
                nested_key = stripped[:-1].strip()
                leaf_key = None
                result.setdefault(top_key, {}).setdefault(nested_key, {})
            continue

        if indent == 4 and stripped.endswith(":"):
            leaf_key = stripped[:-1].strip()
            result[top_key][nested_key][leaf_key] = []
            continue

        if indent >= 6 and stripped.startswith("- "):
            raw_val = _strip_comment(stripped[2:].strip())
            # Preserve quotes semantically before stripping them
            was_dq = raw_val.startswith('"') and raw_val.endswith('"')
            val = raw_val.strip('"')
            if was_dq:
                val = _yaml_unescape(val)
            result[top_key][nested_key][leaf_key].append(val)
            continue

    return result


def validate_action(policies: dict, tool: str, args: dict) -> str:
    """Return one of: 'auto', 'approval', 'denied'."""
    if tool in policies.get("deny", []):
        return "denied"
    # Per-tool arg constraints — currently only web.fetch url denylist.
    if tool == "web.fetch":
        deny = policies.get("constraints", {}).get("web.fetch", {}).get("url_deny_patterns", [])
        u = str(args.get("url", ""))
        for pat in deny:
            if re.search(pat, u):
                return "denied"
    if tool in policies.get("auto", []):
        return "auto"
    if tool in policies.get("approval", []):
        return "approval"
    return policies.get("default", "approval")


# ─── LLM plan step ─────────────────────────────────────────────────────────

def _propose_action(user_request: str, memory_prefix: str, tool_list: list[dict]) -> dict | None:
    """Ask the LLM to pick a tool + args. Returns {tool, args, rationale} or None."""
    tools_desc = "\n".join(f"- {t['name']} {t['schema']}" for t in tool_list)
    prompt = (
        f"{memory_prefix}\n\n"
        f"You are an AI operating system dispatcher. Given the user's request, "
        f"either respond directly (if no tool is needed) OR emit a single JSON object "
        f"of shape {{\"tool\":\"name.subname\", \"args\":{{...}}, \"rationale\":\"...\"}} "
        f"selecting exactly one tool.\n\n"
        f"Available tools:\n{tools_desc}\n\n"
        f"User request: {user_request}\n\n"
        f"Reply with either JSON (for a tool call) or plain text (for a direct answer)."
    )
    body = json.dumps({
        "model": "bitnet",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400, "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(BITNET_URL.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[orchestrator] LLM error: {e}", file=sys.stderr)
        return None
    # Try to parse JSON out of the response.
    m = re.search(r"\{[^{}]*\"tool\"[^{}]*\}", text, re.DOTALL)
    if not m:
        return {"tool": None, "text": text}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"tool": None, "text": text}


# ─── main loop ─────────────────────────────────────────────────────────────

class Orchestrator:
    def __init__(self, auto_approve: bool = False):
        self.policies = _load_policies()
        self.memory = Memory()
        self.auto_approve = auto_approve

    def run(self, mode: str, request: str, session_id: str = "default") -> str:
        # Route to specialised agents first — they have their own prompt shape.
        if mode == "research":
            self.memory.session_add("user", request, session_id=session_id)
            answer = research(request, memory_prefix=self.memory.as_prompt_prefix(session_id))
            self.memory.session_add("assistant", answer, session_id=session_id)
            audit.emit(agent="research", tool="rag.query", args={"q": request},
                       decision="auto", exit_code=0, stdout=answer)
            return answer

        if mode == "ops":
            self.memory.session_add("user", request, session_id=session_id)
            answer = ops(request,
                         memory_prefix=self.memory.as_prompt_prefix(session_id),
                         approver=self._maybe_approve)
            self.memory.session_add("assistant", answer, session_id=session_id)
            return answer

        # Free-form chat: let the LLM pick a tool or answer directly.
        return self._chat(request, session_id=session_id)

    def _chat(self, request: str, session_id: str) -> str:
        self.memory.session_add("user", request, session_id=session_id)
        plan = _propose_action(request, self.memory.as_prompt_prefix(session_id), tools.list_tools())
        if not plan or not plan.get("tool"):
            answer = (plan or {}).get("text", "(no answer)")
            self.memory.session_add("assistant", answer, session_id=session_id)
            audit.emit(agent="chat", tool="llm.answer", args={"request": request},
                       decision="auto", exit_code=0, stdout=answer)
            return answer

        tool_name, args = plan["tool"], plan.get("args", {}) or {}
        decision = validate_action(self.policies, tool_name, args)
        if decision == "denied":
            audit.emit(agent="chat", tool=tool_name, args=args, decision="denied", exit_code=1)
            return f"[denied by policy] tool={tool_name}"

        if decision == "approval" and not self.auto_approve:
            print(f"\n[approval needed] tool={tool_name}  args={args}")
            print(f"  rationale: {plan.get('rationale','')}")
            ok = input("  approve? [y/N] ").strip().lower() == "y"
            if not ok:
                audit.emit(agent="chat", tool=tool_name, args=args, decision="denied", approver="user", exit_code=1)
                return "(user denied)"

        entry = tools.get(tool_name)
        if not entry:
            return f"[unknown tool] {tool_name}"
        fn, _schema = entry
        try:
            result = fn(**args)
            out_str = json.dumps(result, default=str) if not isinstance(result, str) else result
            audit.emit(agent="chat", tool=tool_name, args=args,
                       decision="approved" if decision == "approval" else "auto",
                       approver="user" if decision == "approval" else None,
                       exit_code=0, stdout=out_str)
            self.memory.session_add("assistant", out_str[:2000], session_id=session_id)
            return out_str
        except Exception as e:
            audit.emit(agent="chat", tool=tool_name, args=args, decision="error", exit_code=1, extra={"error": str(e)})
            return f"[error] {tool_name}: {e}"

    def _maybe_approve(self, tool: str, args: dict, rationale: str) -> bool:
        decision = validate_action(self.policies, tool, args)
        if decision == "denied":
            return False
        if decision == "auto" or self.auto_approve:
            return True
        print(f"\n[approval needed] tool={tool}  args={args}")
        print(f"  rationale: {rationale}")
        return input("  approve? [y/N] ").strip().lower() == "y"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["chat", "research", "ops", "list-tools"])
    ap.add_argument("request", nargs="*", help="request text")
    ap.add_argument("--session-id", default="default")
    ap.add_argument("--auto-approve", action="store_true",
                    help="skip approval prompts (dangerous — for CI/testing)")
    args = ap.parse_args()

    if args.mode == "list-tools":
        for t in tools.list_tools():
            print(f"  {t['name']:32}  {t['schema']}")
        return 0

    if not args.request:
        ap.error("request text required")
    request = " ".join(args.request)
    o = Orchestrator(auto_approve=args.auto_approve)
    print(o.run(args.mode, request, session_id=args.session_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
