# Autoclaw — HowTo

> Self-improving AI experiment loop. **You** edit `context.md`. **AI** edits code. **Git** keeps the receipts.

Version 0.1.0 · MIT · [autoclaw.dev](https://autoclaw.dev) · [github.com/dnzengou/autoclaw](https://github.com/dnzengou/autoclaw)

---

## 1. Why

Modern AI coding is a turn-based dialogue: prompt → response → copy/paste → prompt again. That works for one-off changes. It collapses for **iteration** — tuning a model, optimising a query, hunting a perf regression, evolving a prompt.

Autoclaw inverts the loop. You set the goal once in `context.md`. The agent proposes a hypothesis, runs an experiment under a fixed time budget, scores it against your rubric, commits if it improved, reverts if it regressed, and starts the next hypothesis. Indefinitely.

This is the [Karpathy autoresearch pattern](https://github.com/karpathy/autoresearch), productised: no notebooks, no orchestration glue, no API plumbing — one binary, three runtimes (Rust / Go / Python), 14 install channels, one dashboard.

**Use it when:**
- You have a metric you want to push (lower loss, higher F1, faster p99, smaller bundle).
- You want every change tracked in git so nothing is lost.
- You want the AI to do the boring iteration while you set direction.

**Don't use it when:**
- You don't have a metric. (Define one first.)
- The thing being optimised takes hours per run. (Budget too tight.)
- You need real-time interactive control over each step. (Use Claude Code or Cursor instead.)

---

## 2. What

```
┌─ context.md ──────┐    ┌── Hypothesis ──┐    ┌── Run (≤300s) ──┐
│ MISSION           │ →  │ AI proposes    │ →  │ train.py        │
│ CONSTRAINTS       │    │ {hypothesis,   │    │ (your script)   │
│ HYPOTHESES        │    │  params}       │    │                 │
│ LEARNINGS         │    └────────────────┘    └────────┬────────┘
└───────────────────┘                                   │
        ▲                                               ▼
        │                            ┌──── Score (rubric.json) ────┐
        │                            │ - primary_metric: f1_score  │
        │                            │ - higher_is_better: true    │
        │                            │ - fail_threshold: -0.05     │
        │                            └────────┬────────────────────┘
        │                                     │
        │              ┌── Commit/Revert ─────┘
        │              │ git add . && git commit OR git revert
        │              │ Tag best-* on improvement
        │              ▼
        └──── Append result to results.json + dashboard SSE
```

**Three components:**
- **Loop** — the agent (Rust, Go, or Python). Reads context, generates hypotheses, runs experiments, commits or reverts.
- **Server** — HTTP + WebSocket. Serves the dashboard, exposes `/api/*` for SDKs, streams events via SSE.
- **Dashboard** — React/Vite UI (browser) or Tauri shell (desktop + mobile). Live charts, experiment list, context editor.

**API surface (identical across all SDKs):**

| Method | What |
|---|---|
| `status()` | Running? best score? budget left? |
| `experiments()` | All past experiments |
| `best()` | Highest-scoring experiment |
| `get_context()` / `set_context()` | Read/write `context.md` |
| `start()` / `stop()` / `reset()` | Loop control |
| `stream_experiments()` | Live SSE stream of new results |

---

## 3. How — 60-second quickstart

```bash
# Install (pick one)
pip install autoclaw                                                            # Python SDK + CLI
curl -fsSL https://autoclaw.dev/install.sh | sh                                 # binary
docker run -p 8080:8080 -v "$PWD":/app ghcr.io/dnzengou/autoclaw:latest         # container

# Initialize a project
mkdir my-experiment && cd my-experiment
autoclaw init                                                                   # scaffolds context.md, rubric.json, train.py stub

# Edit context.md — your job
$EDITOR context.md

# Set your LLM key (Claude, OpenAI, or DeepSeek — pick one)
export ANTHROPIC_API_KEY=sk-ant-...
# or: export OPENAI_API_KEY=sk-...
# or: export DEEPSEEK_API_KEY=...

# Run the loop — the AI's job
autoclaw run --budget 300                                                       # 300s = ~12 experiments

# Open the dashboard
open http://localhost:8080
```

If no LLM key is set, the agent falls back to a heuristic hypothesis generator — useful for first-run smoke testing without spending a cent.

---

## 4. Installation — all channels

### Pick by stack

| You are a... | Use |
|---|---|
| Python data scientist | `pip install autoclaw` |
| Web developer | `npm i @autoclaw/sdk` |
| Backend / infra engineer | `go get github.com/dnzengou/autoclaw/sdk/go` |
| macOS / Linux user | `brew install dnzengou/tap/autoclaw` |
| Windows user | `scoop install autoclaw` |
| Container / K8s operator | `docker pull ghcr.io/dnzengou/autoclaw:latest` |
| Android user | sideload APK ([SIDELOAD.md](mobile/SIDELOAD.md)) or wait for Play Store ([PLAY_STORE.md](mobile/PLAY_STORE.md)) |
| iOS user | build with `cargo tauri ios build` ([mobile/README.md](mobile/README.md)) |
| Fly.io / Railway / Render | one-click deploy buttons (see below) |

### Detailed install steps

```bash
# Python (recommended for first try)
pip install autoclaw
autoclaw status

# JavaScript / TypeScript
npm i @autoclaw/sdk            # ESM + CJS, types included

# Go
go get github.com/dnzengou/autoclaw/sdk/go

# Homebrew
brew tap dnzengou/tap
brew install autoclaw

# Scoop (Windows)
scoop bucket add dnzengou https://github.com/dnzengou/scoop-bucket
scoop install autoclaw

# Debian / Ubuntu
curl -fsSL https://github.com/dnzengou/autoclaw/releases/latest/download/autoclaw_0.1.0_amd64.deb -o autoclaw.deb
sudo dpkg -i autoclaw.deb

# Direct binary download (Linux/macOS/Windows × amd64/arm64)
# See https://github.com/dnzengou/autoclaw/releases

# Docker
docker run -d -p 8080:8080 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v "$PWD":/app \
  --name autoclaw \
  ghcr.io/dnzengou/autoclaw:latest

# install.sh (POSIX shells, auto-detects OS/arch, SHA256-verified)
curl -fsSL https://autoclaw.dev/install.sh | sh

# install.ps1 (Windows PowerShell, same idea)
iwr -useb https://autoclaw.dev/install.ps1 | iex
```

### One-click cloud deploys

| Provider | Steps |
|---|---|
| **Fly.io** | `git clone https://github.com/dnzengou/autoclaw && cd autoclaw && fly launch` (reads `fly.toml`) |
| **Railway** | Click [Deploy on Railway](https://railway.app/new/template?template=https://github.com/dnzengou/autoclaw) (reads `railway.json`) |
| **Render** | Click [Deploy to Render](https://render.com/deploy?repo=https://github.com/dnzengou/autoclaw) (reads `render.yaml`) |
| **Cloud Run** | `gcloud run deploy autoclaw --image ghcr.io/dnzengou/autoclaw:latest --port 8080 --set-env-vars ANTHROPIC_API_KEY=...` |

### From source

```bash
git clone https://github.com/dnzengou/autoclaw && cd autoclaw

cargo build --release && ./target/release/autoclaw --help        # Rust
go build -o autoclaw-go agent.go && ./autoclaw-go                # Go (single file)
python3 agent.py                                                 # Python (stdlib only)
```

---

## 5. Configuration

### Environment variables

| Var | Default | What |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Claude API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `DEEPSEEK_API_KEY` | — | DeepSeek API key (Go agent) |
| `AUTOCLAW_BUDGET` | `300` | Total experiment time (seconds) |
| `AUTOCLAW_CONTEXT` | `context.md` | Path to context file |
| `AUTOCLAW_PORT` | `8080` | Dashboard / API port |
| `AUTOCLAW_URL` | `http://localhost:8080` | Used by SDKs and mobile app to find the server |
| `RUST_LOG` | `info` | Logging level (Rust core only) |

### `context.md` — the only file you must edit

```markdown
# AUTOCLAW CONTEXT

## MISSION
Push validation F1 above 0.90 on the sentiment dataset.

## CONSTRAINTS
- Time budget: 300s per experiment
- Metric: f1_score (higher is better)
- Target file: train.py
- Don't change the model architecture (only hyperparams + data aug)

## HYPOTHESIS QUEUE
1. Try learning rate 2e-5 with linear warmup
2. Add dropout 0.3
3. Increase batch size to 32

## LEARNINGS
<!-- AI appends here. Leave blank initially. -->
```

### `rubric.json` — scoring

```json
{
  "primary_metric": "f1_score",
  "higher_is_better": true,
  "weights": { "f1_score": 1.0, "inference_time_ms": 0.2 },
  "pass_threshold": 0.85,
  "fail_threshold": -0.05
}
```

`fail_threshold` is relative to current best — `-0.05` means "revert any experiment that scores more than 0.05 below the best so far".

---

## 6. Use cases

### 6.1 Hyperparameter sweep on a small model

```bash
autoclaw init sentiment-tuning
cd sentiment-tuning
# edit context.md: MISSION = "tune lr + dropout for f1"
autoclaw run --budget 1800   # 30 min ~ 60 experiments
```

The agent tries lr/dropout/batch_size combinations. Best run is git-tagged `best-exp-NNN`.

### 6.2 Prompt engineering for an LLM judge

`train.py` calls the LLM, `eval.py` scores responses against a golden set. The agent iterates on the prompt template (stored in `train.py` as a string) until eval accuracy plateaus.

### 6.3 Query / index optimisation

`train.py` runs an EXPLAIN ANALYZE, `eval.py` extracts the cost. The agent tries index variants, query rewrites, materialised views. Best plan is committed.

### 6.4 Frontend perf budget

`train.py` runs Lighthouse against your local dev server, `eval.py` parses LCP/CLS/TBT. The agent tries different bundle splits, lazy-load patterns, image formats.

### 6.5 Self-hosted research lab

Run the server on a Fly.io VM, share `http://your-app.fly.dev` with your team, use the Python or JS SDK from notebooks / dashboards to start runs, query results, stream live updates.

```python
import asyncio
from autoclaw import AutoclawClient

async def main():
    async with AutoclawClient("https://your-app.fly.dev") as c:
        await c.start()
        async for exp in c.stream_experiments():
            print(f"{exp.id} → {exp.score:.4f}")
            if exp.score > 0.95:
                await c.stop()
                break

asyncio.run(main())
```

### 6.6 Mobile dashboard for remote runs

Install the Android APK (sideload or Play Store), set `AUTOCLAW_URL` in app settings to your server's URL, watch experiments stream in from anywhere.

---

## 7. The API in detail

```
GET  /api/status            → { running, total_experiments, best_score, budget_remaining, uptime }
GET  /api/results           → [ Experiment, ... ]
GET  /api/best              → Experiment | null
GET  /api/context           → text/plain (raw context.md)
POST /api/context           → text/plain → updates context.md
POST /api/start             → { status: "started" | "already_running" }
POST /api/stop              → { status: "stopped" }
POST /api/reset             → { status: "reset" }
GET  /events                → SSE stream of experiments + state events
GET  /ws                    → WebSocket stream (same events, binary frames)
```

All SDKs (Python, JS, Go) wrap this surface identically.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Could not parse hypotheses from LLM output` | Model returned text not JSON | Set `--model` to a JSON-capable model (Claude 3 Opus, GPT-4o) |
| Loop exits after first iteration | No LLM key set + fallback exhausted | Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |
| Score = 0 for every experiment | `train.py` not outputting JSON to stdout | Have `train.py` print one JSON line per run |
| `git: command not found` (in Docker) | Old image without git | Use `ghcr.io/dnzengou/autoclaw:latest` (Go pivot includes git) |
| Dashboard blank | CORS / port mismatch | Confirm `AUTOCLAW_URL` matches the server, hard refresh browser |
| Mobile app shows "no server" | `AUTOCLAW_URL` wrong or LAN unreachable | Use `http://10.0.2.2:8080` for Android emulator pointing at host |

---

## 9. Security & privacy

- API keys are read from environment variables, never written to disk or logs.
- The server binds `0.0.0.0:8080` by default. If exposing publicly, put it behind a reverse proxy with auth (Caddy, Cloudflare Tunnel).
- The dashboard CSP only allows scripts from `'self'` + Plausible analytics (cookieless).
- All install scripts verify SHA256 before exec.
- No telemetry. The only outbound calls are to your chosen LLM provider.
- Full policy: [PRIVACY.md](PRIVACY.md).

---

## 10. Next steps

- **Quickstart didn't work?** Open an issue: <https://github.com/dnzengou/autoclaw/issues>
- **Want a feature?** Read [BLUEPRINT.md](BLUEPRINT.md), submit a PR.
- **Mobile?** See [SIDELOAD.md](mobile/SIDELOAD.md) and [PLAY_STORE.md](mobile/PLAY_STORE.md).
- **Architecture deep-dive?** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **Karpathy pattern reference?** <https://github.com/karpathy/autoresearch>
- **Sibling product (one-person AI agency stack):** [Clow.studio](https://clow-tau.vercel.app) by [Desired Solutions](https://desiredsolutions.space).
