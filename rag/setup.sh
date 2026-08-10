#!/usr/bin/env bash
# rag/setup.sh — download embedding model. Assumes ./bitnet/setup.sh already ran
# (we reuse the llama-server binary from bitnet/vendor).
set -euo pipefail

MODEL_ID=""
while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL_ID="$2"; shift 2 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL_DIR="${RAG_MODEL_DIR:-$REPO_ROOT/rag/models}"
MODELS_JSON="$REPO_ROOT/rag/models.json"

need() { command -v "$1" >/dev/null || { echo "missing: $1" >&2; exit 1; }; }
for c in python3 curl; do need "$c"; done

[ -x "$REPO_ROOT/bitnet/vendor/build/bin/llama-server" ] \
  || echo "note: run ./bitnet/setup.sh first to install llama-server" >&2

mkdir -p "$MODEL_DIR"

if [ -z "$MODEL_ID" ]; then
  MODEL_ID="$(python3 -c "import json; print(json.load(open('$MODELS_JSON'))['default'])")"
fi

read -r URL FILENAME SIZE < <(python3 -c "
import json
m = json.load(open('$MODELS_JSON'))['models']['$MODEL_ID']
print(m['url'], m['filename'], m['size_bytes'])
")

OUT="$MODEL_DIR/$FILENAME"
if [ -f "$OUT" ] && [ "$(stat -c%s "$OUT" 2>/dev/null || stat -f%z "$OUT")" = "$SIZE" ]; then
  echo "→ model already present: $OUT"
else
  echo "→ downloading $MODEL_ID (~$((SIZE/1024/1024)) MB) …"
  curl -L --fail --progress-bar -o "$OUT.tmp" "$URL"
  mv "$OUT.tmp" "$OUT"
fi

# Optional text extractors
for c in pdftotext soffice; do
  command -v "$c" >/dev/null && echo "→ $c available (PDF/DOCX extraction OK)" || echo "→ $c missing (skipping .pdf/.docx during ingest)"
done

echo ""
echo "✓ RAG ready. Model: $OUT"
echo "  Serve:  ./rag/serve.sh"
echo "  Ingest: python rag/ingest.py --path <dir>"
echo "  Query:  python rag/query.py 'your question'"
