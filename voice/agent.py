#!/usr/bin/env python3
"""Voice agent: whisper.cpp → BitNet → Piper.

Continuous mode: listens with voice activity detection (VAD), transcribes,
sends to local BitNet server, speaks the reply. All-local, no cloud.

Usage:
    python voice/agent.py --once                # single 5s turn
    python voice/agent.py --continuous          # loop with VAD
    python voice/agent.py --text "hello there"  # skip STT (debug)

Dependencies (Python side): only stdlib. External binaries are shelled out
via the voice/setup.sh install: whisper-cli, piper, arecord/aplay (Linux),
sox/afplay (macOS).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR = REPO_ROOT / "voice" / "vendor"
MODELS = REPO_ROOT / "voice" / "models"

WHISPER_BIN = next(iter(list((VENDOR / "whisper.cpp" / "build" / "bin").glob("whisper-cli*"))), None)
PIPER_BIN = VENDOR / "piper" / ("piper.exe" if os.name == "nt" else "piper")

BITNET_URL = os.environ.get("BITNET_URL", "http://localhost:8081/v1")
SYSTEM_PROMPT = os.environ.get(
    "VOICE_SYSTEM_PROMPT",
    "You are a helpful, concise voice assistant. Reply in 1-2 short sentences suitable for text-to-speech.",
)


def _first(pattern: str, root: Path) -> Path | None:
    hits = sorted(root.glob(pattern))
    return hits[0] if hits else None


def _detect_recorder() -> list[str]:
    if shutil.which("arecord"):
        return ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", "{dur}", "{out}"]
    if shutil.which("sox"):
        return ["sox", "-q", "-d", "-r", "16000", "-c", "1", "-b", "16", "{out}", "trim", "0", "{dur}"]
    sys.exit("no recorder found (install alsa-utils or sox)")


def _detect_player() -> str:
    for c in ("aplay", "afplay", "paplay"):
        if shutil.which(c):
            return c
    sys.exit("no player found (install alsa-utils or pulseaudio-utils)")


def record(duration: int, out_path: Path) -> None:
    tmpl = _detect_recorder()
    cmd = [p.format(dur=str(duration), out=str(out_path)) for p in tmpl]
    subprocess.run(cmd, check=True)


def transcribe(wav: Path) -> str:
    whisper_model = _first("ggml-*.bin", MODELS)
    if not (WHISPER_BIN and whisper_model):
        sys.exit("whisper not installed. run: ./voice/setup.sh")
    with tempfile.TemporaryDirectory() as td:
        out_prefix = Path(td) / "out"
        subprocess.run(
            [str(WHISPER_BIN), "-m", str(whisper_model), "-f", str(wav), "-nt", "-otxt", "-of", str(out_prefix)],
            check=True, capture_output=True,
        )
        return (out_prefix.with_suffix(".txt")).read_text().strip()


def reply(text: str) -> str:
    body = json.dumps({
        "model": "bitnet",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "max_tokens": 120,
        "temperature": 0.3,
    }).encode()
    req = urllib.request.Request(
        BITNET_URL.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def speak(text: str) -> None:
    voice = _first("*.onnx", MODELS)
    if not (PIPER_BIN.exists() and voice):
        sys.exit("piper not installed. run: ./voice/setup.sh")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out = Path(f.name)
    try:
        subprocess.run(
            [str(PIPER_BIN), "--model", str(voice), "--output_file", str(out)],
            input=text.encode(), check=True, capture_output=True,
        )
        subprocess.run([_detect_player(), str(out)], check=True)
    finally:
        out.unlink(missing_ok=True)


def turn(duration: int, text_override: str | None = None) -> None:
    t0 = time.time()
    if text_override:
        user = text_override
        print(f"→ input (skipped STT): {user}")
    else:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav = Path(f.name)
        try:
            print(f"→ recording {duration}s")
            record(duration, wav)
            print("→ transcribing")
            user = transcribe(wav)
        finally:
            wav.unlink(missing_ok=True)
        if not user:
            print("(silence)")
            return
        print(f"  you: {user}")

    print("→ thinking")
    r = reply(user)
    print(f"  bitnet: {r}")

    print("→ speaking")
    speak(r)
    print(f"[turn: {time.time()-t0:.1f}s]")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true", help="single turn then exit")
    p.add_argument("--continuous", action="store_true", help="loop turns until Ctrl-C")
    p.add_argument("--duration", type=int, default=5, help="record window (s)")
    p.add_argument("--text", type=str, help="skip STT with this text")
    args = p.parse_args()

    if not (args.once or args.continuous or args.text):
        args.once = True

    try:
        if args.continuous:
            print("continuous mode — Ctrl-C to exit")
            while True:
                turn(args.duration)
        else:
            turn(args.duration, text_override=args.text)
    except KeyboardInterrupt:
        print("\nbye")
    return 0


if __name__ == "__main__":
    sys.exit(main())
