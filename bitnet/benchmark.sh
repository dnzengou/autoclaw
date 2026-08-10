#!/usr/bin/env bash
# bitnet/benchmark.sh — quick tok/s sanity check.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BITNET_ROOT="${BITNET_ROOT:-$REPO_ROOT/bitnet/vendor}"
MODEL_DIR="${MODEL_DIR:-$REPO_ROOT/bitnet/models}"

CLI="$BITNET_ROOT/build/bin/llama-cli"
MODEL="$(ls -1t "$MODEL_DIR"/*.gguf | head -1)"

[ -x "$CLI" ] || { echo "not built" >&2; exit 1; }
[ -f "$MODEL" ] || { echo "no model" >&2; exit 1; }

echo "→ prompt eval (128 tokens) + generation (128 tokens)"
"$CLI" -m "$MODEL" -p "The quick brown fox" -n 128 -t "$(getconf _NPROCESSORS_ONLN)" 2>&1 | \
  grep -E "eval time|sample time|tokens per second" || true
