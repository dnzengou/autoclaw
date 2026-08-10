# BitNet.cpp — local 1-bit LLM backend for Autoclaw

Runs Microsoft's [BitNet.cpp](https://github.com/microsoft/BitNet) inference engine
on-device. Ternary-weight (1.58-bit) models mean a 2B model fits in ~800 MB RAM and
runs at 20–70 tok/s on a laptop CPU — no GPU, no cloud, no API keys.

## Why this exists

Autoclaw's LLM harness already speaks OpenAI/Anthropic/DeepSeek and "local via
`LOCAL_LLM_URL`". BitNet gives you a **real** local backend that (a) works offline,
(b) processes prompts without leaving the machine, (c) costs €0/req after install.

Enables three use cases the cloud path can't:
- **Privacy-sensitive workflows** (HR, legal, health, defense) where data cannot leave premises
- **Enterprise air-gapped deployments** — no outbound network calls
- **Local voice agent** — pair with `whisper.cpp` (STT) + `piper` (TTS) for a fully-offline assistant

## Quick start

```bash
# From repo root
./bitnet/setup.sh                        # clone, build, download 2B model (~800 MB)
./bitnet/serve.sh                        # llama.cpp-compatible server on :8081
# In another shell:
export LOCAL_LLM_URL=http://localhost:8081/v1
python agent.py --model bitnet --budget 60
```

Windows:
```powershell
.\bitnet\setup.ps1
.\bitnet\serve.ps1
$env:LOCAL_LLM_URL="http://localhost:8081/v1"
python agent.py --model bitnet --budget 60
```

## Model choices (`bitnet/models.json`)

| ID | Params | Size (GGUF) | RAM | Notes |
|---|---|---|---|---|
| `bitnet-b1.58-2B-4T` | 2 B | 795 MB | 1 GB | Default. Trained natively at 1.58-bit on 4 T tokens. |
| `llama3-8b-1.58bit` | 8 B | 3.2 GB | 4 GB | Post-quantized Llama-3. Higher quality, more RAM. |
| `falcon3-7b-1.58bit` | 7 B | 2.8 GB | 3.5 GB | Multilingual. |

Change model:
```bash
./bitnet/setup.sh --model llama3-8b-1.58bit
```

## Files in this dir

- `setup.sh` / `setup.ps1` — clone microsoft/BitNet, build with CMake, download model, verify SHA256
- `serve.sh` / `serve.ps1` — run llama-server on port 8081 (OpenAI-compatible)
- `models.json` — model catalog with URLs and SHA256 sums
- `Modelfile.ollama` — optional Ollama-format wrapper
- `benchmark.sh` — sanity check tok/s on your hardware

## Integration into autoclaw's harness

`agent.py::call_llm()` picks a backend from env vars in this order:
1. `BITNET_URL` — routes to your local BitNet server (this dir)
2. `LOCAL_LLM_URL` — generic OpenAI-compatible endpoint (LM Studio, Ollama, vLLM)
3. `ANTHROPIC_API_KEY` — Claude
4. `OPENAI_API_KEY` — GPT
5. Fallback heuristic (no keys, no server)

Set `BITNET_URL=http://localhost:8081/v1` and every hypothesis/critique call in the
experiment loop runs against the local 1.58-bit model.

## See also

- `../voice/` — voice agent: whisper.cpp → BitNet → Piper TTS
- `../docs/BITNET.md` — full install guide + use case matrix
- Upstream: https://github.com/microsoft/BitNet
