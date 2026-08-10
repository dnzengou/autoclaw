#!/usr/bin/env bash
# voice/ask.sh — one-shot: record 5s → whisper → BitNet → piper → speaker.
# Requires: bitnet server running on localhost:8081, arecord/aplay (Linux) or
# sox (macOS). BitNet server: ./bitnet/serve.sh &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VOICE_ROOT="$REPO_ROOT/voice/vendor"
MODEL_DIR="$REPO_ROOT/voice/models"
BITNET_URL="${BITNET_URL:-http://localhost:8081/v1}"
DURATION="${DURATION:-5}"

WHISPER_BIN="$VOICE_ROOT/whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL="$(ls "$MODEL_DIR"/ggml-*.bin 2>/dev/null | head -1)"
PIPER_BIN="$VOICE_ROOT/piper/piper"
PIPER_VOICE="$(ls "$MODEL_DIR"/*.onnx 2>/dev/null | head -1)"

for f in "$WHISPER_BIN" "$WHISPER_MODEL" "$PIPER_BIN" "$PIPER_VOICE"; do
  [ -e "$f" ] || { echo "missing: $f. Run voice/setup.sh" >&2; exit 1; }
done

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

WAV="$TMPDIR/in.wav"

# 1. record
echo "→ recording ${DURATION}s (speak now)"
if command -v arecord >/dev/null; then
  arecord -q -f S16_LE -r 16000 -c 1 -d "$DURATION" "$WAV"
elif command -v sox >/dev/null; then
  sox -q -d -r 16000 -c 1 -b 16 "$WAV" trim 0 "$DURATION"
else
  echo "no recorder found (install alsa-utils or sox)" >&2; exit 1
fi

# 2. transcribe
echo "→ transcribing"
TEXT="$("$WHISPER_BIN" -m "$WHISPER_MODEL" -f "$WAV" -nt -otxt -of "$TMPDIR/out" 2>/dev/null && cat "$TMPDIR/out.txt")"
TEXT="$(echo "$TEXT" | xargs)"
[ -n "$TEXT" ] || { echo "no speech detected" >&2; exit 1; }
echo "  you: $TEXT"

# 3. BitNet reply (via OpenAI-compatible endpoint)
# Build request body via Python from stdin to sidestep shell-quoting pitfalls.
echo "→ thinking (BitNet)"
REQ_BODY="$(printf '%s' "$TEXT" | python3 -c '
import json, sys
user = sys.stdin.read().strip()
print(json.dumps({
    "model": "bitnet",
    "messages": [
        {"role": "system", "content": "You are a helpful concise assistant. Reply in 1-2 sentences."},
        {"role": "user", "content": user},
    ],
    "max_tokens": 120,
    "temperature": 0.3,
}))
')"

REPLY="$(curl -sf "$BITNET_URL/chat/completions" \
    -H 'Content-Type: application/json' \
    --data "$REQ_BODY" \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"].strip())')"

[ -n "$REPLY" ] || { echo "empty reply from BitNet" >&2; exit 1; }
echo "  bitnet: $REPLY"

# 4. speak
echo "→ speaking"
OUT_WAV="$TMPDIR/out.wav"
echo "$REPLY" | "$PIPER_BIN" --model "$PIPER_VOICE" --output_file "$OUT_WAV" 2>/dev/null

if command -v aplay >/dev/null; then aplay -q "$OUT_WAV"
elif command -v afplay >/dev/null; then afplay "$OUT_WAV"
elif command -v paplay >/dev/null; then paplay "$OUT_WAV"
else echo "no player (install alsa-utils or pulseaudio-utils)" >&2; exit 1
fi
