#!/usr/bin/env python3
"""rag/ingest.py — walk a directory, extract text, chunk, embed, store.

Usage:
    python rag/ingest.py --path ~/Documents/reports
    python rag/ingest.py --path ./notes --db custom.sqlite
    python rag/ingest.py --file specific.pdf --force

Extractors (in order of use):
    .txt .md .py .js .ts .go .rs .java .c .cpp .h .yaml .yml .toml .json .html
        → read as UTF-8 with errors=replace
    .pdf
        → pdftotext (poppler-utils), skip if missing
    .docx
        → soffice --headless --convert-to txt, skip if missing

Embeddings via llama-server --embedding on RAG_URL (default http://localhost:8082/v1).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from store import Store, chunk_id  # noqa: E402

RAG_URL = os.environ.get("RAG_URL", "http://localhost:8082/v1")
DEFAULT_DB = Path(__file__).parent / "store.sqlite"

TEXT_EXTS = {".txt", ".md", ".rst", ".py", ".js", ".ts", ".go", ".rs", ".java",
             ".c", ".cpp", ".h", ".hpp", ".yaml", ".yml", ".toml", ".json",
             ".html", ".xml", ".css", ".sh", ".sql", ".log"}
PDF_EXTS = {".pdf"}
DOC_EXTS = {".docx", ".doc", ".odt"}

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def extract_text(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in TEXT_EXTS:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  skip {path}: {e}", file=sys.stderr)
            return None
    if ext in PDF_EXTS:
        if not _has("pdftotext"):
            return None
        try:
            r = subprocess.run(["pdftotext", "-q", "-nopgbrk", str(path), "-"],
                               capture_output=True, check=True)
            return r.stdout.decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  pdftotext {path}: {e}", file=sys.stderr)
            return None
    if ext in DOC_EXTS:
        if not _has("soffice"):
            return None
        try:
            with subprocess.Popen(["soffice", "--headless", "--cat", str(path)],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as p:
                return p.stdout.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  soffice {path}: {e}", file=sys.stderr)
            return None
    return None


def _has(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []
    # Split on paragraphs first; combine until we hit size.
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 2 <= size:
            buf = f"{buf}\n\n{p}".strip()
        else:
            if buf:
                chunks.append(buf)
            # If a single paragraph is bigger than size, hard-split it.
            while len(p) > size:
                chunks.append(p[:size])
                p = p[size - overlap:]
            buf = p
    if buf:
        chunks.append(buf)
    return chunks


def embed_batch(texts: list[str]) -> np.ndarray:
    url = RAG_URL.rstrip("/") + "/embeddings"
    body = json.dumps({"model": "embedding", "input": texts}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    return np.array([d["embedding"] for d in data["data"]], dtype=np.float32)


def iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    exts = TEXT_EXTS | PDF_EXTS | DOC_EXTS
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts)


def ingest_file(store: Store, path: Path, force: bool = False) -> int:
    sh = sha256_file(path)
    if not force and store.has_source(sh):
        return 0
    # Drop old chunks for this file (re-ingest replaces cleanly)
    store.delete_by_doc_path(str(path))
    text = extract_text(path)
    if not text:
        return 0
    chunks = chunk_text(text)
    if not chunks:
        return 0
    embeds = embed_batch(chunks)
    records = [
        (chunk_id(str(path), i, sh), str(path), i, c, embeds[i], sh)
        for i, c in enumerate(chunks)
    ]
    return store.upsert(records)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", type=Path, help="Directory or file to ingest")
    ap.add_argument("--file", type=Path, help="Single file (alias for --path)")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite path (default {DEFAULT_DB})")
    ap.add_argument("--force", action="store_true", help="Re-ingest files even if hash unchanged")
    args = ap.parse_args()
    root = args.path or args.file
    if not root or not root.exists():
        ap.error("--path or --file must exist")
    # CLI-supplied path: resolve to canonical form so the ingested doc_path
    # is stable across relative/symlink variations. Not a security boundary
    # (the CLI is trusted); the network surface (rag/server.py) enforces
    # a root allowlist separately.
    root = root.resolve()

    store = Store(args.db)
    files = iter_files(root)
    print(f"→ {len(files)} candidate file(s) under {root}")
    total = 0
    for i, f in enumerate(files, 1):
        n = ingest_file(store, f, force=args.force)
        marker = f"[{n:3d} chunks]" if n else "[skip]"
        print(f"  ({i}/{len(files)}) {marker} {f}")
        total += n
    print(f"→ done. {total} new chunks. Store has {store.count()} total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
