#!/usr/bin/env bash
# voice/setup.sh — clone whisper.cpp + piper, build, download small default models.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VOICE_ROOT="${VOICE_ROOT:-$REPO_ROOT/voice/vendor}"
MODEL_DIR="${MODEL_DIR:-$REPO_ROOT/voice/models}"
MODELS_JSON="$REPO_ROOT/voice/models.json"

need() { command -v "$1" >/dev/null || { echo "missing: $1" >&2; exit 1; }; }
for c in git cmake make curl python3; do need "$c"; done

# ─── whisper.cpp ─────────────────────────────────────────────────────────────
WHISPER_DIR="$VOICE_ROOT/whisper.cpp"
if [ ! -d "$WHISPER_DIR/.git" ]; then
  echo "→ cloning whisper.cpp"
  git clone --depth 1 https://github.com/ggerganov/whisper.cpp "$WHISPER_DIR"
fi
if [ ! -x "$WHISPER_DIR/build/bin/whisper-cli" ] && [ ! -x "$WHISPER_DIR/main" ]; then
  echo "→ building whisper.cpp"
  cmake -S "$WHISPER_DIR" -B "$WHISPER_DIR/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
  cmake --build "$WHISPER_DIR/build" --config Release -j"$(getconf _NPROCESSORS_ONLN)"
fi

# ─── Piper (release binary — faster than compiling) ─────────────────────────
PIPER_DIR="$VOICE_ROOT/piper"
if [ ! -x "$PIPER_DIR/piper" ]; then
  echo "→ downloading piper release"
  mkdir -p "$PIPER_DIR"
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64)   ASSET="piper_linux_x86_64.tar.gz" ;;
    Linux-aarch64)  ASSET="piper_linux_aarch64.tar.gz" ;;
    Darwin-arm64)   ASSET="piper_macos_aarch64.tar.gz" ;;
    Darwin-x86_64)  ASSET="piper_macos_x64.tar.gz" ;;
    *)              echo "unsupported piper platform: $(uname -sm)" >&2; exit 1 ;;
  esac
  curl -L --fail -o "$PIPER_DIR/piper.tgz" "https://github.com/rhasspy/piper/releases/latest/download/$ASSET"
  tar -xzf "$PIPER_DIR/piper.tgz" -C "$PIPER_DIR" --strip-components=1
  rm "$PIPER_DIR/piper.tgz"
fi

# ─── models ──────────────────────────────────────────────────────────────────
mkdir -p "$MODEL_DIR"

W_URL=$(python3 -c "import json; m=json.load(open('$MODELS_JSON')); v=m['whisper']['variants'][m['whisper']['default']]; print(v['url'])")
W_OUT="$MODEL_DIR/$(basename "$W_URL")"
[ -f "$W_OUT" ] || { echo "→ downloading whisper model"; curl -L --fail -o "$W_OUT" "$W_URL"; }

P_JSON=$(python3 -c "import json; m=json.load(open('$MODELS_JSON')); v=m['piper']['variants'][m['piper']['default']]; print(v['onnx'], v['json'])")
for U in $P_JSON; do
  OUT="$MODEL_DIR/$(basename "$U")"
  [ -f "$OUT" ] || { echo "→ downloading $(basename "$U")"; curl -L --fail -o "$OUT" "$U"; }
done

echo ""
echo "✓ voice stack ready"
echo "  whisper: $WHISPER_DIR/build/bin/whisper-cli"
echo "  piper:   $PIPER_DIR/piper"
echo "  models:  $MODEL_DIR/"
echo "  try:     ./voice/ask.sh"
