#!/usr/bin/env bash
# bitnet/setup.sh — one-shot: clone microsoft/BitNet, build, download model.
#
# Usage:
#   ./bitnet/setup.sh                             # default 2B model
#   ./bitnet/setup.sh --model llama3-8b-1.58bit   # pick from models.json
#   ./bitnet/setup.sh --no-model                  # build only, skip download
#
# Env:
#   BITNET_ROOT   install dir (default: ./bitnet/vendor)
#   MODEL_DIR     model store  (default: ./bitnet/models)
#   JOBS          parallel build jobs (default: nproc)

set -euo pipefail

MODEL_ID=""
DOWNLOAD_MODEL=1

while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL_ID="$2"; shift 2 ;;
    --no-model) DOWNLOAD_MODEL=0; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BITNET_ROOT="${BITNET_ROOT:-$REPO_ROOT/bitnet/vendor}"
MODEL_DIR="${MODEL_DIR:-$REPO_ROOT/bitnet/models}"
MODELS_JSON="$REPO_ROOT/bitnet/models.json"
JOBS="${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1" >&2; exit 1; }; }
for c in git cmake python3 make curl sha256sum; do need "$c"; done

# ─── 1. Clone microsoft/BitNet ───────────────────────────────────────────────
if [ ! -d "$BITNET_ROOT/.git" ]; then
  echo "→ cloning microsoft/BitNet …"
  git clone --recursive --depth 1 https://github.com/microsoft/BitNet "$BITNET_ROOT"
else
  echo "→ updating microsoft/BitNet …"
  git -C "$BITNET_ROOT" pull --ff-only
  git -C "$BITNET_ROOT" submodule update --init --recursive
fi

# ─── 2. Build ────────────────────────────────────────────────────────────────
if [ -x "$BITNET_ROOT/build/bin/llama-cli" ] || [ -x "$BITNET_ROOT/build/bin/llama-cli.exe" ]; then
  echo "→ build already present, skipping (rm -rf bitnet/vendor/build to rebuild)"
else
  echo "→ configuring CMake (Release, jobs=$JOBS) …"
  cd "$BITNET_ROOT"
  # Python env for BitNet's build helpers
  python3 -m venv .venv
  # shellcheck disable=SC1091
  . .venv/bin/activate
  python3 -m pip install --quiet --upgrade pip
  python3 -m pip install --quiet -r requirements.txt
  # setup_env.py picks kernel type (i2_s / tl1 / tl2) based on CPU + model
  python3 setup_env.py --hf-repo microsoft/BitNet-b1.58-2B-4T-gguf --quant-type i2_s
  echo "→ build OK: $BITNET_ROOT/build/bin/"
fi

# ─── 3. Download model ───────────────────────────────────────────────────────
if [ "$DOWNLOAD_MODEL" -eq 0 ]; then
  echo "→ --no-model set, skipping download"
  exit 0
fi

mkdir -p "$MODEL_DIR"
if [ -z "$MODEL_ID" ]; then
  MODEL_ID="$(python3 -c "import json,sys; print(json.load(open('$MODELS_JSON'))['default'])")"
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
  echo "→ downloading $MODEL_ID ($(numfmt --to=iec-i --suffix=B $SIZE 2>/dev/null || echo $SIZE bytes)) …"
  curl -L --fail --progress-bar -o "$OUT.tmp" "$URL"
  mv "$OUT.tmp" "$OUT"
fi

echo ""
echo "✓ ready. Model: $OUT"
echo "  Start server: ./bitnet/serve.sh"
echo "  Or run once:  $BITNET_ROOT/build/bin/llama-cli -m $OUT -p 'Hello' -n 32"
