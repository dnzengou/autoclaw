#!/usr/bin/env python3
"""autoclaw_os.py — the Private AI OS entry point.

One command, six layers:

    autoclaw-os ingest <path>              # RAG layer: add docs to knowledge base
    autoclaw-os memory add personal ...    # Memory layer: personal/org KV
    autoclaw-os research "<question>"      # Agents layer: RAG-cited answer
    autoclaw-os ops     "<task>"           # Agents layer: multi-step with approvals
    autoclaw-os chat    "<request>"        # Free-form dispatcher
    autoclaw-os status                     # All layers: what's up + counts
    autoclaw-os serve                      # HTTP surface (bitnet + rag + agents)

Env:
    BITNET_URL         (default http://localhost:8081/v1)
    RAG_URL            (default http://localhost:8082/v1)
    AUTOCLAW_MEMORY_DB (default memory/memory.sqlite)
    AUTOCLAW_SESSION_ID (default 'default')
    AUTOCLAW_AUDIT_LOG (default ~/.autoclaw/audit.jsonl)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))


def _cmd_status(_args) -> int:
    from memory.manager import Memory
    from rag.store import Store as RagStore

    bitnet_url = os.environ.get("BITNET_URL", "http://localhost:8081/v1")
    rag_url = os.environ.get("RAG_URL", "http://localhost:8082/v1")

    def _ping(url: str, path: str = "/health") -> str:
        try:
            with urllib.request.urlopen(url.rstrip("/v1") + path, timeout=2) as r:
                return f"up ({r.status})"
        except Exception as e:
            return f"down ({type(e).__name__})"

    rag = RagStore(REPO_ROOT / "rag" / "store.sqlite")
    mem = Memory()
    print("Layer 1 — Runtime (BitNet):     ", _ping(bitnet_url))
    print("Layer 3 — RAG (embeddings):     ", _ping(rag_url))
    print(f"Layer 2 — Memory:                {len(mem.personal_list())} personal / {len(mem.org_list())} org keys")
    print(f"Layer 3 — RAG store:             {rag.count()} chunks")
    print(f"Layer 4 — Audit log:             {os.environ.get('AUTOCLAW_AUDIT_LOG', str(Path.home()/'.autoclaw/audit.jsonl'))}")
    print(f"Layer 5 — Connectors:            email={_email_configured()} · gh={_gh_available()}")
    return 0


def _email_configured() -> str:
    have = all(os.environ.get(k) for k in ("EMAIL_HOST", "EMAIL_USER", "EMAIL_PASSWORD"))
    return "ok" if have else "not configured"


def _gh_available() -> str:
    from shutil import which
    return "ok" if which("gh") else "missing"


def _cmd_ingest(args) -> int:
    subprocess.run([sys.executable, "rag/ingest.py", "--path", str(args.path)], check=True, cwd=REPO_ROOT)
    return 0


def _cmd_research(args) -> int:
    from agents.orchestrator import Orchestrator
    print(Orchestrator().run("research", " ".join(args.request), session_id=args.session_id))
    return 0


def _cmd_ops(args) -> int:
    from agents.orchestrator import Orchestrator
    o = Orchestrator(auto_approve=args.auto_approve)
    print(o.run("ops", " ".join(args.request), session_id=args.session_id))
    return 0


def _cmd_chat(args) -> int:
    from agents.orchestrator import Orchestrator
    o = Orchestrator(auto_approve=args.auto_approve)
    print(o.run("chat", " ".join(args.request), session_id=args.session_id))
    return 0


def _cmd_memory(args) -> int:
    # Delegate to memory/manager.py CLI unchanged.
    subprocess.run([sys.executable, "memory/manager.py", *args.rest], check=True, cwd=REPO_ROOT)
    return 0


def _cmd_serve(args) -> int:
    """Fan-out: start BitNet + RAG servers + Python orchestrator HTTP wrapper."""
    procs = []
    try:
        print("→ starting BitNet server on :8081")
        procs.append(subprocess.Popen(["./bitnet/serve.sh"], cwd=REPO_ROOT))
        time.sleep(2)
        print("→ starting RAG embedding server on :8082")
        procs.append(subprocess.Popen(["./rag/serve.sh"], cwd=REPO_ROOT))
        time.sleep(2)
        print("→ starting agent HTTP endpoint on :8083")
        procs.append(subprocess.Popen([sys.executable, "rag/server.py", "--port", "8083"], cwd=REPO_ROOT))
        print("\n✓ Private AI OS is up. Ctrl-C to stop.")
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\n→ shutting down")
    finally:
        for p in procs:
            try: p.terminate()
            except Exception: pass
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="autoclaw-os", description=__doc__.strip().split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show layer status").set_defaults(fn=_cmd_status)

    p = sub.add_parser("ingest", help="Add a file/dir to the RAG store")
    p.add_argument("path", type=Path); p.set_defaults(fn=_cmd_ingest)

    p = sub.add_parser("research", help="Ask a question against the knowledge base")
    p.add_argument("request", nargs="+"); p.add_argument("--session-id", default="default")
    p.set_defaults(fn=_cmd_research)

    p = sub.add_parser("ops", help="Run an ops task with approvals")
    p.add_argument("request", nargs="+"); p.add_argument("--session-id", default="default")
    p.add_argument("--auto-approve", action="store_true")
    p.set_defaults(fn=_cmd_ops)

    p = sub.add_parser("chat", help="Free-form dispatcher (LLM picks a tool)")
    p.add_argument("request", nargs="+"); p.add_argument("--session-id", default="default")
    p.add_argument("--auto-approve", action="store_true")
    p.set_defaults(fn=_cmd_chat)

    p = sub.add_parser("memory", help="Personal / org / session memory (passthrough)")
    p.add_argument("rest", nargs=argparse.REMAINDER); p.set_defaults(fn=_cmd_memory)

    sub.add_parser("serve", help="Start BitNet + RAG + agent servers together").set_defaults(fn=_cmd_serve)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
