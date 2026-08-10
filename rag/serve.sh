#!/usr/bin/env bash
# rag/serve.sh — run llama-server in embedding mode on :8082.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BITNET_ROOT="${BITNET_ROOT:-$REPO_ROOT/bitnet/vendor}"
MODEL_DIR="${RAG_MODEL_DIR:-$REPO_ROOT/rag/models}"
PORT="${RAG_PORT:-8082}"
CTX="${RAG_CTX:-2048}"
THREADS="${RAG_THREADS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"

SERVER_BIN="$BITNET_ROOT/build/bin/llama-server"
[ -x "$SERVER_BIN" ] || { echo "not built. run: ./bitnet/setup.sh" >&2; exit 1; }

MODEL="$(ls -1t "$MODEL_DIR"/*.gguf 2>/dev/null | head -1)"
[ -f "$MODEL" ] || { echo "no embedding model. run: ./rag/setup.sh" >&2; exit 1; }

echo "→ embedding server: $(basename "$MODEL") on :$PORT (ctx=$CTX, threads=$THREADS)"
echo "  Endpoint: POST http://localhost:$PORT/v1/embeddings"

exec "$SERVER_BIN" \
  --model "$MODEL" \
  --host 0.0.0.0 \
  --port "$PORT" \
  --embedding \
  --ctx-size "$CTX" \
  --threads "$THREADS"
