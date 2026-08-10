#!/usr/bin/env python3
"""memory/manager.py — persistent memory API + CLI.

Three tiers: personal (per-user KV), session (append-only chat log with rolling
summary), org (versioned team-shared KV). Stdlib SQLite only.

CLI:
    add personal <key> <value>       set personal memory
    get personal <key>               retrieve
    list personal                    list all
    add org <key> <value>            set org memory (versioned; auto-increments)
    session-add <role> <content>     append to current session
    session-context [session_id]     return rolling context (with summary)
    session-summarize [session_id]   force-summarize old turns

Env:
    AUTOCLAW_MEMORY_DB              path to sqlite (default memory/memory.sqlite)
    AUTOCLAW_SESSION_ID             default session id ("default")
    AUTOCLAW_USER                    owner for personal memory ($USER by default)
    MEMORY_SESSION_MAX_TURNS         summarize when session exceeds this (default 20)
    BITNET_URL                       endpoint used to write summaries (optional)
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_FILE = Path(__file__).parent / "schema.sql"
DEFAULT_DB = Path(os.environ.get("AUTOCLAW_MEMORY_DB", Path(__file__).parent / "memory.sqlite"))
DEFAULT_SESSION = os.environ.get("AUTOCLAW_SESSION_ID", "default")
DEFAULT_USER = os.environ.get("AUTOCLAW_USER") or os.environ.get("USER") or os.environ.get("USERNAME") or "default"
MAX_TURNS = int(os.environ.get("MEMORY_SESSION_MAX_TURNS", "20"))
BITNET_URL = os.environ.get("BITNET_URL")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Memory:
    def __init__(self, db_path: Path = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.executescript(SCHEMA_FILE.read_text())
        self.conn.commit()

    # ── personal ───────────────────────────────────────────────────────────
    def personal_set(self, key: str, value: str, owner: str = DEFAULT_USER) -> None:
        now = _now()
        self.conn.execute(
            """INSERT INTO personal_memory (owner, key, value, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(owner, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (owner, key, value, now, now),
        )
        self.conn.commit()

    def personal_get(self, key: str, owner: str = DEFAULT_USER) -> str | None:
        r = self.conn.execute("SELECT value FROM personal_memory WHERE owner=? AND key=?",
                              (owner, key)).fetchone()
        return r[0] if r else None

    def personal_list(self, owner: str = DEFAULT_USER) -> list[tuple[str, str]]:
        return list(self.conn.execute(
            "SELECT key, value FROM personal_memory WHERE owner=? ORDER BY key", (owner,)
        ))

    # ── org ────────────────────────────────────────────────────────────────
    def org_set(self, key: str, value: str, author: str | None = None) -> int:
        cur = self.conn.execute("SELECT MAX(version) FROM org_memory WHERE key=?", (key,))
        prev = cur.fetchone()[0]
        v = (prev or 0) + 1
        now = _now()
        self.conn.execute(
            "INSERT INTO org_memory (key, value, version, author, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (key, value, v, author or DEFAULT_USER, now, now),
        )
        self.conn.commit()
        return v

    def org_get(self, key: str) -> str | None:
        r = self.conn.execute(
            "SELECT value FROM org_memory WHERE key=? ORDER BY version DESC LIMIT 1", (key,)
        ).fetchone()
        return r[0] if r else None

    def org_list(self) -> list[tuple[str, str, int]]:
        # latest version per key
        return list(self.conn.execute("""
            SELECT o1.key, o1.value, o1.version
            FROM org_memory o1
            WHERE o1.version = (SELECT MAX(o2.version) FROM org_memory o2 WHERE o2.key = o1.key)
            ORDER BY o1.key
        """))

    # ── session ────────────────────────────────────────────────────────────
    def session_add(self, role: str, content: str, session_id: str = DEFAULT_SESSION) -> int:
        self.conn.execute(
            "INSERT INTO session_memory (session_id, role, content, created_at, tokens) VALUES (?,?,?,?,?)",
            (session_id, role, content, _now(), _approx_tokens(content)),
        )
        self.conn.commit()
        self._maybe_summarize(session_id)
        return self.session_turn_count(session_id)

    def session_turn_count(self, session_id: str = DEFAULT_SESSION) -> int:
        r = self.conn.execute(
            "SELECT COUNT(*) FROM session_memory WHERE session_id=? AND role IN ('user','assistant')",
            (session_id,),
        ).fetchone()
        return r[0] if r else 0

    def session_context(self, session_id: str = DEFAULT_SESSION) -> list[dict]:
        """Return list of {role, content} suitable for a chat completion request."""
        rows = list(self.conn.execute(
            "SELECT role, content FROM session_memory WHERE session_id=? ORDER BY id", (session_id,)
        ))
        return [{"role": r, "content": c} for r, c in rows]

    def _maybe_summarize(self, session_id: str) -> None:
        n = self.session_turn_count(session_id)
        if n <= MAX_TURNS:
            return
        # Take the oldest half; summarize; delete originals; insert 'summary' at position 0.
        half = n // 2
        rows = list(self.conn.execute("""
            SELECT id, role, content FROM session_memory
            WHERE session_id=? AND role IN ('user','assistant')
            ORDER BY id ASC LIMIT ?
        """, (session_id, half)))
        if not rows:
            return
        summary_text = _summarize([(r[1], r[2]) for r in rows])
        ids = [r[0] for r in rows]
        # Delete the originals
        self.conn.executemany("DELETE FROM session_memory WHERE id=?", [(i,) for i in ids])
        # Insert one summary row (prepend by assigning a small id via ROWID reuse — easier: just insert; sort by created_at is fine)
        self.conn.execute(
            "INSERT INTO session_memory (session_id, role, content, created_at, tokens) VALUES (?,?,?,?,?)",
            (session_id, "summary", summary_text, _now(), _approx_tokens(summary_text)),
        )
        self.conn.commit()

    # ── helpers ────────────────────────────────────────────────────────────
    def as_prompt_prefix(self, session_id: str = DEFAULT_SESSION, owner: str = DEFAULT_USER) -> str:
        """Assemble a compact preamble that agents can prepend to any LLM call."""
        p_lines = [f"- {k}: {v}" for k, v in self.personal_list(owner)]
        o_lines = [f"- {k}: {v}" for k, v, _v in self.org_list()]
        s_summary = ""
        for role, content in self.conn.execute(
            "SELECT role, content FROM session_memory WHERE session_id=? AND role='summary' ORDER BY id",
            (session_id,),
        ):
            s_summary += content + "\n"

        parts = []
        if p_lines:
            parts.append("User memory:\n" + "\n".join(p_lines))
        if o_lines:
            parts.append("Team memory:\n" + "\n".join(o_lines))
        if s_summary.strip():
            parts.append("Session summary:\n" + s_summary.strip())
        return "\n\n".join(parts)


def _approx_tokens(text: str) -> int:
    # 1 token ≈ 4 chars is a rough English default; good enough for budgeting.
    return max(1, len(text) // 4)


def _summarize(turns: list[tuple[str, str]]) -> str:
    """Summarize a list of (role, content) turns.

    Uses BitNet if BITNET_URL is set; falls back to a naive first-lines join.
    """
    body = "\n".join(f"{r}: {c}" for r, c in turns)
    if not BITNET_URL:
        # Fallback: take first sentence of each turn, joined.
        heads = []
        for r, c in turns:
            first = c.strip().split(".")[0][:120]
            heads.append(f"{r}: {first}")
        return "Summary of earlier turns:\n" + "\n".join(heads)

    prompt = (
        "Summarize the following conversation turns as a compact 3-5 sentence recap. "
        "Preserve concrete decisions, names, numbers, and open questions. Drop pleasantries.\n\n"
        + body
    )
    try:
        req = urllib.request.Request(
            BITNET_URL.rstrip("/") + "/chat/completions",
            data=json.dumps({
                "model": "bitnet",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300, "temperature": 0.2,
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return "Summary: " + json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[memory] summarize error: {e}", file=sys.stderr)
        return _summarize(turns[:1])  # degrade to trivial fallback


# ─── CLI ───────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add"); a.add_argument("tier", choices=["personal", "org"]); a.add_argument("key"); a.add_argument("value")
    g = sub.add_parser("get"); g.add_argument("tier", choices=["personal", "org"]); g.add_argument("key")
    l = sub.add_parser("list"); l.add_argument("tier", choices=["personal", "org"])
    sa = sub.add_parser("session-add"); sa.add_argument("role", choices=["user", "assistant", "system"]); sa.add_argument("content"); sa.add_argument("--session-id", default=DEFAULT_SESSION)
    sc = sub.add_parser("session-context"); sc.add_argument("--session-id", default=DEFAULT_SESSION); sc.add_argument("--format", choices=["json", "prefix"], default="prefix")
    ss = sub.add_parser("session-summarize"); ss.add_argument("--session-id", default=DEFAULT_SESSION)

    args = ap.parse_args()
    m = Memory()

    if args.cmd == "add":
        if args.tier == "personal": m.personal_set(args.key, args.value); print("ok")
        else: v = m.org_set(args.key, args.value); print(f"ok (v{v})")
    elif args.cmd == "get":
        v = m.personal_get(args.key) if args.tier == "personal" else m.org_get(args.key)
        print(v if v is not None else "(not set)")
    elif args.cmd == "list":
        rows = m.personal_list() if args.tier == "personal" else m.org_list()
        for r in rows: print("  ", *r)
    elif args.cmd == "session-add":
        n = m.session_add(args.role, args.content, session_id=args.session_id)
        print(f"ok (turn {n})")
    elif args.cmd == "session-context":
        if args.format == "json":
            print(json.dumps(m.session_context(args.session_id), indent=2))
        else:
            print(m.as_prompt_prefix(args.session_id))
    elif args.cmd == "session-summarize":
        m._maybe_summarize(args.session_id); print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
