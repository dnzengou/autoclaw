#!/usr/bin/env python3
"""rag/query.py — embed a question, return top-k chunks with citations.

Usage:
    python rag/query.py "supplier risk in the last five years"
    python rag/query.py "explain the auth module" --k 10 --db custom.sqlite
    python rag/query.py "..." --format json      # for pipeline use
    python rag/query.py "..." --context          # prompt-ready block for LLM
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from store import Store  # noqa: E402
import numpy as np  # noqa: E402

RAG_URL = os.environ.get("RAG_URL", "http://localhost:8082/v1")
DEFAULT_DB = Path(__file__).parent / "store.sqlite"


def embed_one(text: str) -> np.ndarray:
    url = RAG_URL.rstrip("/") + "/embeddings"
    body = json.dumps({"model": "embedding", "input": [text]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return np.array(data["data"][0]["embedding"], dtype=np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+", help="Query text")
    ap.add_argument("--k", type=int, default=5, help="Top-k results")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--format", choices=["text", "json", "context"], default="text")
    ap.add_argument("--min-score", type=float, default=0.0, help="Filter by cosine score")
    args = ap.parse_args()

    q = " ".join(args.query)
    store = Store(args.db)
    if store.count() == 0:
        print("(store empty — run rag/ingest.py first)", file=sys.stderr)
        return 1

    hits = [h for h in store.query(embed_one(q), top_k=args.k) if h["score"] >= args.min_score]

    if args.format == "json":
        print(json.dumps(hits, indent=2))
    elif args.format == "context":
        # Prompt-ready block for an LLM
        print(f"Relevant context (top {len(hits)} chunks from local knowledge base):\n")
        for i, h in enumerate(hits, 1):
            print(f"[{i}] {h['doc_path']}#chunk{h['chunk_idx']} (score={h['score']:.3f})")
            print(h["text"])
            print()
    else:  # text
        print(f"query: {q}\n")
        for i, h in enumerate(hits, 1):
            snippet = h["text"][:200].replace("\n", " ")
            print(f"  [{i}] {h['score']:.3f}  {h['doc_path']}:{h['chunk_idx']}")
            print(f"       {snippet}…\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
