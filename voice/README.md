# Voice Agent — fully-offline STT → LLM → TTS

Whisper.cpp (transcription) → BitNet (reasoning) → Piper (synthesis). All local, all
private. Runs on a laptop CPU. Zero cloud API calls.

## Pipeline

```
mic → 16 kHz PCM → whisper.cpp → text
                                  ↓
                        BitNet.cpp (llama-server)
                                  ↓
                                text → Piper TTS → speakers
```

## Quick start

```bash
# One-time: install engines + models
./bitnet/setup.sh                    # BitNet + 2B model (~800 MB)
./voice/setup.sh                     # whisper.cpp + Piper + tiny models (~500 MB)

# Start BitNet server (once)
./bitnet/serve.sh &

# One-shot voice interaction (records 5s, responds, speaks reply)
./voice/ask.sh

# Or continuous conversation loop (voice activity detection)
python voice/agent.py --continuous
```

## Files

- `agent.py` — Python entry point; wires whisper → BitNet → Piper
- `setup.sh` — clone whisper.cpp + Piper, build, download models
- `ask.sh` — 5-second one-shot: record → transcribe → respond → speak
- `models.json` — whisper (`ggml-tiny.en.bin`, 75 MB) + Piper voice (`en_US-amy-medium.onnx`, ~60 MB)
- `systemd/voice-agent.service` — Linux service unit (long-running listener)
- `launchd/dev.autoclaw.voice.plist` — macOS launchd unit
- `windows/register-service.ps1` — Windows Service via NSSM

## Latency budget (typical laptop CPU)

| Stage | Model | ~ms |
|---|---|---|
| STT | whisper tiny.en | 200–400 |
| Reasoning | BitNet 2B, 100-token response | 1500–3000 |
| TTS | Piper amy-medium | 100–300 |
| **Total** | | **~2–4 s** |

Swap `tiny.en` → `base.en` for higher-quality transcription (~800 ms latency).
Swap BitNet 2B → 8B for higher-quality reasoning (~4× latency, ~4× RAM).

## Use cases

- **Kiosk assistants** — retail, hospitality, healthcare check-in — sensitive
  utterances never leave the box.
- **Field ops (offline)** — logistics, defense, emergency response — device works
  with zero connectivity.
- **Accessibility** — voice control for users who can't type; PII stays local.
- **Meeting notes** — transcribe + summarise into `.md` without uploading audio.

## Privacy contract

- No outbound network requests during voice interaction. `agent.py` opens sockets
  only to `localhost:8081` (BitNet). Confirm with `strace`/`Process Monitor`.
- Audio buffers held in RAM, not written to disk (unless `--save-audio` flag set).
- Transcripts optionally logged to `.autoclaw/voice-log.jsonl` (off by default).
