#!/usr/bin/env python3
"""rag/server.py — HTTP wrapper around ingest + query.

Endpoints:
    POST /rag/ingest  {"path": "..."}          → {"chunks_added": N}
    POST /rag/query   {"q": "...", "k": 5}     → [{doc_path, chunk_idx, text, score}, ...]
    GET  /rag/status                           → {"chunks": N, "db": "..."}

Usage:
    python rag/server.py --port 8083
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ingest import ingest_file, iter_files  # noqa: E402
from query import embed_one  # noqa: E402
from store import Store  # noqa: E402

DEFAULT_DB = Path(__file__).parent / "store.sqlite"
_ingest_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, obj) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if n == 0:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except Exception:
            return {}

    def log_message(self, fmt: str, *args) -> None:  # quieter default
        sys.stderr.write(f"[rag] {self.address_string()} - {fmt % args}\n")

    def do_GET(self) -> None:
        if self.path == "/rag/status":
            store = Store(self.server.db_path)
            return self._send_json(200, {"chunks": store.count(), "db": str(self.server.db_path)})
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        body = self._read_body()
        if self.path == "/rag/ingest":
            p = Path(body.get("path", ""))
            if not p.exists():
                return self._send_json(400, {"error": f"path not found: {p}"})
            store = Store(self.server.db_path)
            with _ingest_lock:
                total = 0
                for f in iter_files(p):
                    total += ingest_file(store, f, force=bool(body.get("force")))
            return self._send_json(200, {"chunks_added": total, "total": store.count()})
        if self.path == "/rag/query":
            q = body.get("q", "").strip()
            if not q:
                return self._send_json(400, {"error": "missing 'q'"})
            k = int(body.get("k", 5))
            store = Store(self.server.db_path)
            return self._send_json(200, store.query(embed_one(q), top_k=k))
        self._send_json(404, {"error": "not found"})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("RAG_SERVER_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("RAG_SERVER_PORT", "8083")))
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    srv = HTTPServer((args.host, args.port), Handler)
    srv.db_path = args.db  # type: ignore[attr-defined]
    print(f"[rag] serving on http://{args.host}:{args.port}  db={args.db}")
    print(f"      POST /rag/ingest  POST /rag/query  GET /rag/status")
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
