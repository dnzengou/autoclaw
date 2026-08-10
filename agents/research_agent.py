"""agents/research_agent.py — RAG-backed research agent.

Given a question, retrieves top-k chunks from the local RAG store, prompts
BitNet with the chunks as context, returns a cited answer. Read-only; no
approval needed.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag.query import embed_one  # noqa: E402
from rag.store import Store  # noqa: E402

BITNET_URL = os.environ.get("BITNET_URL", "http://localhost:8081/v1")
STORE_PATH = Path(__file__).resolve().parent.parent / "rag" / "store.sqlite"


def research(question: str, k: int = 5, memory_prefix: str = "") -> str:
    store = Store(STORE_PATH)
    if store.count() == 0:
        return ("(no knowledge base — run rag/ingest.py to add documents, then retry. "
                "In the meantime, I can only answer from general knowledge — which for "
                "an offline BitNet model may be limited.)")
    hits = store.query(embed_one(question), top_k=k)
    if not hits:
        return "(no relevant chunks found)"

    context_block = "\n\n".join(
        f"[{i+1}] {h['doc_path']}#chunk{h['chunk_idx']} (score {h['score']:.2f})\n{h['text']}"
        for i, h in enumerate(hits)
    )
    prompt = (
        f"{memory_prefix}\n\n" if memory_prefix else ""
    ) + (
        "You are a research assistant. Answer the question using ONLY the provided "
        "context chunks. Cite chunks by their [N] tag. If the context does not contain "
        "the answer, say so explicitly — do not fabricate.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n\n"
        "Answer (with citations):"
    )
    body = json.dumps({
        "model": "bitnet",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 600, "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(BITNET_URL.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            answer = json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[research error: {e}]"

    # Append the source list for transparency.
    sources = "\n\nSources:\n" + "\n".join(
        f"  [{i+1}] {h['doc_path']} (chunk {h['chunk_idx']}, score {h['score']:.2f})"
        for i, h in enumerate(hits)
    )
    return answer + sources
