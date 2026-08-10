# BitNet.cpp — install & use guide

Local 1.58-bit LLM inference for Autoclaw. Runs on CPU. No cloud. No API keys.

- [Why BitNet](#why-bitnet)
- [Install as standalone app](#install-as-standalone-app)
- [Docker image (privacy edition)](#docker-image-privacy-edition)
- [Voice agent](#voice-agent)
- [Low-hanging-fruit use cases](#low-hanging-fruit-use-cases)
- [Ops runbook](#ops-runbook)

## Why BitNet

Microsoft's [BitNet.cpp](https://github.com/microsoft/BitNet) is an inference
runtime for **native 1.58-bit** (ternary weight: {-1, 0, +1}) LLMs. Compared to a
FP16 model of the same architecture:

- **~10× smaller RAM** — a 2B model fits in ~800 MB
- **~4–7× faster on CPU** — no GPU required
- **~50% less energy** — quantified in Microsoft's paper
- **Same-quality outputs at ≤ 3B params** — degrades gracefully beyond

Concretely: `BitNet-b1.58-2B-4T` runs at **20–70 tok/s** on a mid-range laptop
(Ryzen 7 / M2), enough for interactive latency (~2 s per short response).

## Install as standalone app

### macOS (Homebrew tap)
```bash
brew install autoclaw/tap/autoclaw
autoclaw install-bitnet          # clones microsoft/BitNet, builds, downloads 2B model
autoclaw serve --with-bitnet     # starts autoclaw + BitNet in one process
open http://localhost:8080       # dashboard
```

### Windows (Scoop)
```powershell
scoop bucket add autoclaw https://github.com/dnzengou/scoop-autoclaw
scoop install autoclaw
autoclaw install-bitnet
autoclaw serve --with-bitnet
Start-Process http://localhost:8080
```

Register as a Windows service (auto-start on boot):
```powershell
# Requires nssm — install: scoop install nssm
.\bitnet\windows\install-service.ps1
```

### Linux (Debian/Ubuntu .deb)
```bash
wget https://github.com/dnzengou/autoclaw/releases/latest/download/autoclaw_amd64.deb
sudo dpkg -i autoclaw_amd64.deb
autoclaw install-bitnet
sudo cp bitnet/systemd/autoclaw-bitnet.service /etc/systemd/system/
sudo systemctl enable --now autoclaw-bitnet
```

### Linux/macOS (curl-pipe one-liner)
```bash
curl -fsSL autoclaw.dev/install.sh | sh -s -- --with-bitnet
```

### Android (Termux)
```bash
pkg install git cmake python make clang curl
git clone --depth 1 https://github.com/dnzengou/autoclaw && cd autoclaw
./bitnet/setup.sh --model bitnet-b1.58-2B-4T
./bitnet/serve.sh
```
The 2B model runs at ~10 tok/s on a Pixel-class CPU.

### iOS
BitNet.cpp compiles for iOS via the llama.cpp iOS example. The Tauri 2 shell in
`mobile/` embeds it as a background thread. TestFlight distribution only —
Apple's on-device ML guidance changes yearly; consult
[Apple's ML guidelines](https://developer.apple.com/machine-learning/) before
shipping.

## Docker image (privacy edition)

Single image with autoclaw + BitNet server + 2B model baked in. Runs offline.

```bash
docker build -f Dockerfile.bitnet -t autoclaw:bitnet .
docker run --rm -p 8080:8080 -p 8081:8081 autoclaw:bitnet
```

For air-gapped deployments:
```bash
docker save autoclaw:bitnet | gzip > autoclaw-bitnet.tar.gz
# transfer via USB / secure channel, then on target:
gunzip -c autoclaw-bitnet.tar.gz | docker load
```

Image size: ~2 GB (base + BitNet build + model). Startup: ~5 s.

## Voice agent

whisper.cpp (STT) → BitNet (reasoning) → Piper (TTS). All-local, no cloud.

```bash
./voice/setup.sh          # ~500 MB: whisper tiny.en + Piper en_US voice
./bitnet/serve.sh &       # background
./voice/ask.sh            # 5-sec record, transcribe, respond, speak
# or Python loop:
python voice/agent.py --continuous
```

Latency: **~2–4 s per turn** on a laptop CPU. See [voice/README.md](../voice/README.md)
for the pipeline diagram and model swaps.

## Low-hanging-fruit use cases

| Use case | Why BitNet wins | Deploy path |
|---|---|---|
| **HR document Q&A** — CVs, employee handbooks, offer letters | GDPR/PII stays on-prem; no vendor DPA needed | Docker image behind reverse proxy on internal network |
| **Legal draft review** — NDAs, contracts, redlines | Attorney-client privilege intact; no data leaves firm | Homebrew install on partner laptop + `--with-bitnet` |
| **Healthcare intake triage** — patient chief-complaint parsing | HIPAA-aligned; audit trail in `.autoclaw/deals.json` | .deb on hospital kiosk + systemd service |
| **Field-ops voice assistant** — logistics, defense, disaster response | Works offline; no cell/wifi dependency | APK on Android tablet + BitNet in Termux |
| **Retail kiosk / hotel check-in** — voice concierge in local language | Piper supports 40+ voices; no cloud latency spikes | Docker on mini-PC + touch screen |
| **Meeting transcription + summary** — internal strategy sessions | Nothing uploaded to Otter/Zoom AI | `voice/agent.py --transcribe-only` + summarize via `agent.py` |
| **Air-gapped SOC (security ops)** — log/alert enrichment | Cannot rely on external LLM APIs by policy | `docker save` + USB transfer to isolated network |
| **Autoclaw experiment loop for regulated ML** — pharma, finance | Every hypothesis run against data that can't leave premises | `BITNET_URL=... python agent.py` |
| **Edu/tutoring on old hardware** — 4-year-old Chromebooks | Runs where GPT-hosted apps hit rate limits or paywalls | .deb + browser at `localhost:8080` |
| **Personal journaling / therapy notes** — nothing uploaded, ever | Real "your data stays yours" | brew install on your laptop |

### ARM (Adoption · Retention · Monetization) analysis

**Adoption** — the 15-second install (`curl … | sh -s -- --with-bitnet`) is the same
lever the `?demo=1` static demo added at the funnel top: zero-friction first-experience.
The **install itself** becomes the aha (`I ran an LLM offline, on this laptop`).

**Retention** — the BitNet path is the only realistic route for users whose employer
policy blocks cloud LLM APIs (large chunks of finance/health/legal). Once they wire
`BITNET_URL` into their workflow, the switching cost is high — competitors would need
to solve the same local-inference problem.

**Monetization** — the community edition is free forever (MIT). Enterprise SKUs sit
naturally on top: signed models, RBAC, audit-log-to-SIEM, per-tenant model isolation,
support SLA. Docker image is the packaging surface; Kubernetes operator is the next
step up.

## Ops runbook

### Health checks
```bash
curl http://localhost:8081/health         # BitNet server
curl http://localhost:8080/api/status     # autoclaw
```

### Logs
- Systemd:  `journalctl -u autoclaw-bitnet -f`
- launchd:  `tail -f /usr/local/var/log/autoclaw/bitnet.log`
- Windows:  `Get-Content bitnet\bitnet.log -Wait`
- Docker:   `docker logs -f <container>`

### Tuning
| Symptom | Fix |
|---|---|
| Slow response (>5s/turn) | Drop to 2B model; increase `--threads` to physical-core count |
| Out-of-memory | Reduce `--ctx-size` (2048 → 1024); use `q2_k` quant variant |
| Truncated replies | Increase `--n-predict` from 512 to 1024 |
| Voice cutoff | Extend `--duration` in `voice/ask.sh` from 5 to 8 |

### Update the model
```bash
rm bitnet/models/*.gguf
./bitnet/setup.sh --model llama3-8b-1.58bit
sudo systemctl restart autoclaw-bitnet   # or docker restart
```

### Uninstall
```bash
# systemd
sudo systemctl disable --now autoclaw-bitnet
sudo rm /etc/systemd/system/autoclaw-bitnet.service
# files
rm -rf bitnet/vendor bitnet/models voice/vendor voice/models
```

## Security model

- **No outbound network** during inference — verify with `ss -tunapl` (Linux) or Little
  Snitch (macOS). Sockets only bind to `localhost:8080/8081` by default.
- **Model provenance** — SHA256 sums pinned in `bitnet/models.json`. Setup script
  verifies before use.
- **Non-root** — all systemd/docker paths run as `autoclaw` user.
- **Read-only filesystem** — supported via systemd `ProtectSystem=strict`; docker
  compose can add `read_only: true` with tmpfs for `/tmp`.
- **Audit** — set `AUTOCLAW_AUDIT_LOG=/var/log/autoclaw/audit.jsonl` to record every
  prompt→response pair (off by default).
