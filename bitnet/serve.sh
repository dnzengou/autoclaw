#!/usr/bin/env bash
# bitnet/serve.sh — start the llama-server bundled with microsoft/BitNet.
# Exposes an OpenAI-compatible HTTP API on port 8081 by default.
#
# Env:
#   BITNET_PORT     listen port (default 8081)
#   BITNET_CTX      context window (default 2048)
#   BITNET_THREADS  CPU threads (default: physical cores)
#   MODEL_FILE      explicit path to .gguf (default: newest in bitnet/models/)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BITNET_ROOT="${BITNET_ROOT:-$REPO_ROOT/bitnet/vendor}"
MODEL_DIR="${MODEL_DIR:-$REPO_ROOT/bitnet/models}"
PORT="${BITNET_PORT:-8081}"
CTX="${BITNET_CTX:-2048}"
THREADS="${BITNET_THREADS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"

SERVER_BIN="$BITNET_ROOT/build/bin/llama-server"
[ -x "$SERVER_BIN" ] || { echo "not built. run: ./bitnet/setup.sh" >&2; exit 1; }

MODEL="${MODEL_FILE:-$(ls -1t "$MODEL_DIR"/*.gguf 2>/dev/null | head -1)}"
[ -f "$MODEL" ] || { echo "no model in $MODEL_DIR. run: ./bitnet/setup.sh" >&2; exit 1; }

echo "→ serving $(basename "$MODEL") on :$PORT (ctx=$CTX, threads=$THREADS)"
echo "  OpenAI-compatible: http://localhost:$PORT/v1/chat/completions"
echo "  Autoclaw:          export BITNET_URL=http://localhost:$PORT/v1"

exec "$SERVER_BIN" \
  --model "$MODEL" \
  --host 0.0.0.0 \
  --port "$PORT" \
  --ctx-size "$CTX" \
  --threads "$THREADS" \
  --n-predict 512
