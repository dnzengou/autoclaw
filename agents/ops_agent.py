"""agents/ops_agent.py — operations agent: email + github + web.

Handles inbox summarization, github triage, and web fetches. Write actions
(email.send, github.create_issue) are gated by the approver callback.

The agent runs a small planning loop: LLM proposes a plan (list of tool calls),
each is validated + approved individually, results feed back into the next
step.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents import audit, tools  # noqa: E402

BITNET_URL = os.environ.get("BITNET_URL", "http://localhost:8081/v1")
MAX_STEPS = int(os.environ.get("OPS_MAX_STEPS", "5"))


def _llm(prompt: str, max_tokens: int = 400) -> str:
    body = json.dumps({
        "model": "bitnet",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(BITNET_URL.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def _extract_json(text: str) -> dict | None:
    m = re.search(r"\{[\s\S]*?\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def ops(request: str, memory_prefix: str = "",
        approver: Callable[[str, dict, str], bool] | None = None) -> str:
    """Run the ops agent loop and return the final human-readable answer."""
    scratch: list[str] = []
    ops_tools = [t for t in tools.list_tools()
                 if t["name"].startswith(("email.", "github.", "web.", "files.write", "memory."))]
    tools_desc = "\n".join(f"- {t['name']} {t['schema']}" for t in ops_tools)

    for step in range(MAX_STEPS):
        prompt = (
            f"{memory_prefix}\n\n" if memory_prefix else ""
        ) + (
            "You are an operations agent for a Private AI OS. You have access to these tools:\n"
            f"{tools_desc}\n\n"
            "Rules:\n"
            "1) Break the request into one tool call at a time.\n"
            "2) After each tool result, decide whether more work is needed.\n"
            "3) When done, respond with a final answer (no JSON, plain text).\n\n"
            f"User request: {request}\n\n"
            f"Scratchpad so far:\n{chr(10).join(scratch) if scratch else '(empty)'}\n\n"
            "Reply with either:\n"
            '  {\"tool\":\"name.subname\", \"args\":{...}, \"rationale\":\"...\"}\n'
            "  — or —\n"
            "  A final answer (plain text starting with `FINAL:`)."
        )
        reply = _llm(prompt, max_tokens=500)

        if reply.startswith("FINAL:"):
            return reply[len("FINAL:"):].strip()

        plan = _extract_json(reply)
        if not plan or "tool" not in plan:
            scratch.append(f"[step {step+1}] LLM produced no tool call — stopping.\nReply was:\n{reply[:400]}")
            return "\n".join(scratch) + "\n\n(no final answer produced)"

        tool_name = plan["tool"]
        args = plan.get("args", {}) or {}
        rationale = plan.get("rationale", "")

        entry = tools.get(tool_name)
        if not entry:
            scratch.append(f"[step {step+1}] unknown tool: {tool_name}")
            continue

        # Approval gate.
        if approver and not approver(tool_name, args, rationale):
            audit.emit(agent="ops", tool=tool_name, args=args, decision="denied",
                       approver="user", exit_code=1)
            scratch.append(f"[step {step+1}] denied: {tool_name}")
            continue

        fn, _schema = entry
        try:
            result = fn(**args)
            result_str = json.dumps(result, default=str) if not isinstance(result, str) else result
            audit.emit(agent="ops", tool=tool_name, args=args,
                       decision="auto",  # approver already recorded above via prompt
                       exit_code=0, stdout=result_str)
            scratch.append(f"[step {step+1}] {tool_name} → {result_str[:600]}")
        except Exception as e:
            audit.emit(agent="ops", tool=tool_name, args=args, decision="error",
                       exit_code=1, extra={"error": str(e)})
            scratch.append(f"[step {step+1}] {tool_name} failed: {e}")

    # Ran out of steps — summarize.
    return "\n".join(scratch) + f"\n\n(hit MAX_STEPS={MAX_STEPS}; incomplete)"
