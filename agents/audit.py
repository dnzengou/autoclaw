"""agents/audit.py — append-only JSONL audit sink.

One line per action. Consumable by any SIEM. Includes tool, args, decision,
approver, exit code, and a sha256 hash of stdout (not the content itself, to
keep the audit log lean and privacy-safe by default).
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

AUDIT_PATH = Path(os.environ.get("AUTOCLAW_AUDIT_LOG",
                                 Path.home() / ".autoclaw" / "audit.jsonl"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_short(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8", errors="replace")
    return hashlib.sha256(data).hexdigest()[:16]


def emit(*,
         agent: str,
         tool: str,
         args: dict,
         decision: str,
         approver: str | None = None,
         exit_code: int | None = None,
         stdout: str | bytes | None = None,
         stderr: str | bytes | None = None,
         extra: dict | None = None) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": _now(),
        "agent": agent,
        "tool": tool,
        "args": args,
        "decision": decision,   # auto | approved | denied | error
        "approver": approver,
        "exit": exit_code,
        "stdout_hash": sha256_short(stdout) if stdout else None,
        "stderr_hash": sha256_short(stderr) if stderr else None,
    }
    if extra:
        record.update(extra)
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
