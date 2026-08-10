"""SQLite-backed vector store. Stdlib + numpy only.

Schema:
    chunks(id TEXT PK, doc_path TEXT, chunk_idx INT, text TEXT,
           embedding BLOB, ingested_at TEXT, source_hash TEXT)

Embeddings are stored as np.float32 byte arrays. Cosine similarity is a numpy
dot product on pre-normalized vectors. Brute force scan works up to ~100k
chunks on a laptop (~50 ms/query). Swap in hnswlib beyond that.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id           TEXT PRIMARY KEY,
    doc_path     TEXT NOT NULL,
    chunk_idx    INTEGER NOT NULL,
    text         TEXT NOT NULL,
    embedding    BLOB NOT NULL,
    ingested_at  TEXT NOT NULL,
    source_hash  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_doc_path ON chunks(doc_path);
CREATE INDEX IF NOT EXISTS idx_source_hash ON chunks(source_hash);
"""


def chunk_id(doc_path: str, chunk_idx: int, source_hash: str) -> str:
    h = hashlib.sha256(f"{doc_path}::{chunk_idx}::{source_hash}".encode()).hexdigest()[:16]
    return f"{Path(doc_path).name}:{chunk_idx}:{h}"


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert(self, records: Iterable[tuple[str, str, int, str, np.ndarray, str]]) -> int:
        """Insert or replace chunks. records = [(id, doc_path, chunk_idx, text, embedding, source_hash)]."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows = [
            (rid, dp, ci, txt, _norm(emb).astype(np.float32).tobytes(), now, sh)
            for rid, dp, ci, txt, emb, sh in records
        ]
        self.conn.executemany(
            "INSERT OR REPLACE INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?)", rows
        )
        self.conn.commit()
        return len(rows)

    def delete_by_source_hash(self, source_hash: str) -> int:
        c = self.conn.execute("DELETE FROM chunks WHERE source_hash = ?", (source_hash,))
        self.conn.commit()
        return c.rowcount

    def delete_by_doc_path(self, doc_path: str) -> int:
        c = self.conn.execute("DELETE FROM chunks WHERE doc_path = ?", (doc_path,))
        self.conn.commit()
        return c.rowcount

    def has_source(self, source_hash: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM chunks WHERE source_hash = ? LIMIT 1", (source_hash,)
        ).fetchone() is not None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def all_embeddings(self) -> tuple[np.ndarray, list[tuple[str, str, int, str]]]:
        """Load every embedding into a matrix + parallel metadata list.

        Returns (matrix [N, D], meta [(id, doc_path, chunk_idx, text), ...]).
        Kept simple: fits in RAM up to ~100k chunks × 1024-dim × 4B ≈ 400 MB.
        """
        rows = list(self.conn.execute("SELECT id, doc_path, chunk_idx, text, embedding FROM chunks"))
        if not rows:
            return np.zeros((0, 0), dtype=np.float32), []
        embeds = np.stack([np.frombuffer(r[4], dtype=np.float32) for r in rows])
        meta = [(r[0], r[1], r[2], r[3]) for r in rows]
        return embeds, meta

    def query(self, query_vec: np.ndarray, top_k: int = 5) -> list[dict]:
        embeds, meta = self.all_embeddings()
        if not len(meta):
            return []
        q = _norm(query_vec).astype(np.float32)
        sims = embeds @ q  # cosine (pre-normalized)
        top_idx = np.argsort(-sims)[:top_k]
        return [
            {
                "id": meta[i][0],
                "doc_path": meta[i][1],
                "chunk_idx": meta[i][2],
                "text": meta[i][3],
                "score": float(sims[i]),
            }
            for i in top_idx
        ]


def _norm(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v if n == 0 else v / n
