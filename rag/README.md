# RAG — local knowledge engine (Layer 3)

Local semantic search over your files. Embeds with a small GGUF model served
by llama-server (same runtime as BitNet). Vector store: SQLite (stdlib).
Zero external services. Zero cloud calls.

## Quick start

```bash
# 1. Install engine + default embedding model
./rag/setup.sh                                # downloads nomic-embed-text-v1.5 (~90 MB)

# 2. Serve the embedding model (separate llama-server on :8082)
./rag/serve.sh &

# 3. Ingest a directory
python rag/ingest.py --path ~/Documents/reports

# 4. Query
python rag/query.py "supplier risk over the last five years"
# Returns top-k chunks with file paths + line numbers + relevance scores
```

## Files

- `models.json` — 3 GGUF embedding model variants (nomic 137M / bge 33M / e5 560M multilingual)
- `setup.sh` — download model + verify SHA256
- `serve.sh` — llama-server on :8082 with `--embedding` mode
- `ingest.py` — walk dir → extract text (txt/md/pdf/docx/py/js/go/rs) → chunk → embed → store
- `query.py` — embed query → cosine top-k → format results with citations
- `store.py` — SQLite BLOB-column vector store (stdlib + numpy only)
- `server.py` — HTTP wrapper: `POST /rag/ingest` `POST /rag/query` (mounts onto autoclaw HTTP server)

## Design notes

- **Extractors**: stdlib for txt/md/code; shell out to `pdftotext` (poppler-utils) for PDFs; `soffice --headless --convert-to txt` for docx if libreoffice present. If neither is installed, we skip those file types and warn.
- **Chunking**: 800-char windows with 150-char overlap. Splits on paragraph boundaries when possible. Deterministic — re-ingest produces same chunk IDs.
- **Storage**: `store.sqlite` with schema `(id TEXT PRIMARY KEY, doc_path TEXT, chunk_idx INT, text TEXT, embedding BLOB, ingested_at TEXT)`. Embedding is `np.float32.tobytes()`. Cosine similarity is numpy dot product (embeddings pre-normalized).
- **Scale**: brute-force cosine works well up to ~100k chunks (~50 ms/query on a laptop CPU). Beyond that, swap `store.py::query()` for hnswlib.
- **Reranking**: none by default. Add cross-encoder rerank later if precision matters more than latency.

## Integration into autoclaw

`agent.py` gains a `--rag` flag: when set, hypothesis-generation prompts get a
"relevant prior context" block prepended, pulled from top-5 chunks matching the
current `context.md`. Also exposed via HTTP: `POST /rag/query {"q":"..."}` on the
autoclaw port (default 8080).

The voice agent (`voice/agent.py`) reads RAG results into the BitNet prompt when
`AUTOCLAW_RAG=1` — enables "ask the assistant about the meeting notes you took
yesterday" flows.

## Model swap

```bash
./rag/setup.sh --model bge-small-en-v1.5      # 33 MB, fastest, English only
./rag/setup.sh --model multilingual-e5-large  # 336 MB, 100+ languages
```

Restart `./rag/serve.sh` after swapping. **Warning**: changing model dim
requires re-ingesting the corpus (old embeddings incompatible).

## See also

- `../bitnet/` — LLM runtime; RAG uses the same llama-server binary in `--embedding` mode
- `../memory/` — persistent user memory (Layer 2)
- `../agents/research_agent.py` — RAG-backed research agent
- `../docs/PRIVATE_AI_OS.md` — the 6-layer story
