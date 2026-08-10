"""agents/tools.py — the tool registry.

A tool is a callable with a stable name (e.g. "rag.query"), a JSON schema for
its inputs, and a Python function that receives kwargs and returns a
serializable result. The orchestrator dispatches by name.

New tools should be added here so they inherit the policy engine automatically.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Import module surfaces lazily inside each function so unrelated failures
# don't crash the registry at import.

Tool = Callable[..., Any]
_registry: dict[str, tuple[Tool, dict]] = {}


def register(name: str, schema: dict) -> Callable[[Tool], Tool]:
    def deco(fn: Tool) -> Tool:
        _registry[name] = (fn, schema)
        return fn
    return deco


def get(name: str) -> tuple[Tool, dict] | None:
    return _registry.get(name)


def list_tools() -> list[dict]:
    return [{"name": n, "schema": s} for n, (_fn, s) in _registry.items()]


# ─── rag ───────────────────────────────────────────────────────────────────
@register("rag.query", {"q": "string", "k": "int?"})
def rag_query(q: str, k: int = 5) -> list[dict]:
    from rag.query import embed_one
    from rag.store import Store
    return Store(REPO_ROOT / "rag" / "store.sqlite").query(embed_one(q), top_k=k)


@register("rag.status", {})
def rag_status() -> dict:
    from rag.store import Store
    s = Store(REPO_ROOT / "rag" / "store.sqlite")
    return {"chunks": s.count()}


# ─── memory ────────────────────────────────────────────────────────────────
@register("memory.get", {"tier": "personal|org", "key": "string"})
def memory_get(tier: str, key: str) -> str | None:
    from memory.manager import Memory
    m = Memory()
    return m.personal_get(key) if tier == "personal" else m.org_get(key)


@register("memory.list", {"tier": "personal|org"})
def memory_list(tier: str) -> list:
    from memory.manager import Memory
    m = Memory()
    return m.personal_list() if tier == "personal" else m.org_list()


@register("memory.session_add", {"role": "user|assistant|system", "content": "string", "session_id": "string?"})
def memory_session_add(role: str, content: str, session_id: str = "default") -> int:
    from memory.manager import Memory
    return Memory().session_add(role, content, session_id=session_id)


@register("memory.session_context", {"session_id": "string?"})
def memory_session_context(session_id: str = "default") -> str:
    from memory.manager import Memory
    return Memory().as_prompt_prefix(session_id)


# ─── web ───────────────────────────────────────────────────────────────────
@register("web.fetch", {"url": "string", "max_bytes": "int?"})
def web_fetch(url: str, max_bytes: int = 200_000) -> dict:
    from connectors.web_fetch import fetch
    return fetch(url, max_bytes=max_bytes)


# ─── email ─────────────────────────────────────────────────────────────────
@register("email.list_inbox", {"limit": "int?"})
def email_list_inbox(limit: int = 20) -> list[dict]:
    from connectors.email_imap import list_inbox
    return list_inbox(limit=limit)


@register("email.get_message", {"uid": "int"})
def email_get_message(uid: int) -> dict:
    from connectors.email_imap import get_message
    return get_message(uid)


# ─── github (via gh CLI, no OAuth setup needed if user is already logged in) ─
@register("github.list_issues", {"repo": "string?", "state": "string?"})
def github_list_issues(repo: str | None = None, state: str = "open") -> list[dict]:
    args = ["gh", "issue", "list", "--json", "number,title,state,author,createdAt", "--state", state]
    if repo:
        args += ["--repo", repo]
    r = subprocess.run(args, capture_output=True, text=True, check=True, timeout=30)
    import json as _json
    return _json.loads(r.stdout)


@register("github.list_pulls", {"repo": "string?", "state": "string?"})
def github_list_pulls(repo: str | None = None, state: str = "open") -> list[dict]:
    args = ["gh", "pr", "list", "--json", "number,title,state,author,createdAt,mergeable", "--state", state]
    if repo:
        args += ["--repo", repo]
    r = subprocess.run(args, capture_output=True, text=True, check=True, timeout=30)
    import json as _json
    return _json.loads(r.stdout)


@register("github.get_issue", {"number": "int", "repo": "string?"})
def github_get_issue(number: int, repo: str | None = None) -> dict:
    args = ["gh", "issue", "view", str(number), "--json", "number,title,body,state,author,createdAt,comments"]
    if repo:
        args += ["--repo", repo]
    r = subprocess.run(args, capture_output=True, text=True, check=True, timeout=30)
    import json as _json
    return _json.loads(r.stdout)


# ─── files ─────────────────────────────────────────────────────────────────
@register("files.write", {"path": "string", "content": "string"})
def files_write(path: str, content: str) -> dict:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"path": str(p), "bytes": len(content.encode())}
