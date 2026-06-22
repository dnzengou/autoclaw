# Autoclaw

> Self-improving AI experiment loop. **You** edit `context.md`. **AI** edits code. **Git** keeps the receipts.

[![CI](https://github.com/dnzengou/autoclaw/actions/workflows/ci.yml/badge.svg)](https://github.com/dnzengou/autoclaw/actions/workflows/ci.yml)
[![Docker](https://github.com/dnzengou/autoclaw/actions/workflows/docker.yml/badge.svg)](https://github.com/dnzengou/autoclaw/actions/workflows/docker.yml)
[![Android](https://github.com/dnzengou/autoclaw/actions/workflows/android.yml/badge.svg)](https://github.com/dnzengou/autoclaw/actions/workflows/android.yml)
[![Release](https://img.shields.io/github/v/release/dnzengou/autoclaw?display_name=tag&sort=semver)](https://github.com/dnzengou/autoclaw/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![pip](https://img.shields.io/pypi/v/autoclaw?label=pip)](https://pypi.org/project/autoclaw/)
[![npm](https://img.shields.io/npm/v/@autoclaw/sdk?label=npm)](https://www.npmjs.com/package/@autoclaw/sdk)
[![GHCR](https://img.shields.io/badge/ghcr-autoclaw-blue?logo=docker)](https://github.com/dnzengou/autoclaw/pkgs/container/autoclaw)

```
┌─ context.md ──────┐    ┌── Hypothesis ──┐    ┌── Run (≤300s) ──┐
│ MISSION           │ →  │ AI proposes    │ →  │ train.py        │
│ CONSTRAINTS       │    │ {hypothesis,   │    │ (your script)   │
│ HYPOTHESES        │    │  params}       │    │                 │
│ LEARNINGS         │    └────────────────┘    └────────┬────────┘
└───────────────────┘                                   │
        ▲                                               ▼
        │              ┌── Score → Commit / Revert ────┐
        │              │ rubric.json + git              │
        └──────────────┴────────────────────────────────┘
```

## Install in 30 seconds

```bash
pip install autoclaw                                       # Python SDK + CLI
curl -fsSL https://autoclaw.dev/install.sh | sh            # native binary
docker run -p 8080:8080 ghcr.io/dnzengou/autoclaw:latest   # container
```

Other channels: `npm i @autoclaw/sdk` · `brew install dnzengou/tap/autoclaw` · `scoop install autoclaw` · `go get github.com/dnzengou/autoclaw/sdk/go` · Android APK · `.deb` · Fly.io · Railway · Render. Full matrix: [DISTRIBUTION.md](DISTRIBUTION.md).

## Quickstart

```bash
mkdir my-experiment && cd my-experiment
autoclaw init
export ANTHROPIC_API_KEY=sk-ant-...                        # or OPENAI / DEEPSEEK
$EDITOR context.md
autoclaw run --budget 300                                  # ~12 experiments
open http://localhost:8080
```

## Read this next

| Document | When to read |
|---|---|
| [HOWTO.md](HOWTO.md) | First time using Autoclaw — why/what/how + 6 use cases + full API reference |
| [DISTRIBUTION.md](DISTRIBUTION.md) | Pick the right install channel for your stack |
| [BLUEPRINT.md](BLUEPRINT.md) | Architecture, roadmap, release flow |
| [mobile/SIDELOAD.md](mobile/SIDELOAD.md) | Install the Android APK without the Play Store |
| [mobile/PLAY_STORE.md](mobile/PLAY_STORE.md) | Publish the mobile app to Google Play |
| [PRIVACY.md](PRIVACY.md) | What we collect (nothing) and why |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the Rust core + server + dashboard fit together |
| [docs/CLAUDE_COWORK_INTEGRATION.md](docs/CLAUDE_COWORK_INTEGRATION.md) | Integrating with Claude Cowork |

## SDKs

```python
# Python
import asyncio
from autoclaw import AutoclawClient

async def main():
    async with AutoclawClient("http://localhost:8080") as c:
        await c.start()
        async for exp in c.stream_experiments():
            print(f"{exp.id} → {exp.score:.4f}")
            if exp.score > 0.9:
                await c.stop(); break

asyncio.run(main())
```

```ts
// TypeScript
import { AutoclawClient } from "@autoclaw/sdk";

const c = new AutoclawClient({ baseUrl: "http://localhost:8080" });
await c.start();
for await (const exp of c.streamExperiments()) {
  console.log(`${exp.id} → ${exp.score.toFixed(4)}`);
}
```

```go
// Go
import autoclaw "github.com/dnzengou/autoclaw/sdk/go"

c := autoclaw.NewClient("http://localhost:8080")
c.Start(ctx)
out := make(chan autoclaw.Experiment)
go c.StreamExperiments(ctx, out)
for e := range out { fmt.Printf("%s → %.4f\n", e.ID, e.Score) }
```

## How it works

1. **You** write goals in `context.md` (mission, constraints, hypothesis queue).
2. **Agent** asks an LLM (Claude, GPT, DeepSeek, or local) for hypotheses.
3. **Loop** runs each hypothesis as a `train.py` invocation under a fixed time budget.
4. **Eval** scores results against `rubric.json`.
5. **Git** commits improvements (`exp-NNN` + `best-*` tag on a new high score) and reverts regressions.
6. **Dashboard** streams everything live via SSE / WebSocket.
7. **Repeat** until budget exhausted.

Three runtime variants ship in this repo, all sharing the same API surface:
- **Rust** (`src/`, ~2650 lines) — production server, full feature set.
- **Go** (`agent.go`, single file) — cross-compiles trivially, default in the Docker image.
- **Python** (`agent.py`, stdlib only) — for notebooks, smoke testing, no compile.

## Roadmap

✅ Multi-channel distribution · ✅ Cross-platform CI · ✅ Tauri 2 mobile shell · 🔲 Multi-agent · 🔲 Plugin system · 🔲 Distributed training · 🔲 Community leaderboard.

Track open work: [BLUEPRINT.md](BLUEPRINT.md).

## Origins & family

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch). Built for [Claude Cowork](https://claude.ai).

Part of the [Desired Solutions](https://desiredsolutions.space) product family. Sibling product: [Clow.studio](https://clow-tau.vercel.app) — one-person AI agency stack (9 Telegram bots, 8 web apps, 5 templates).

## License

MIT — see [LICENSE](LICENSE).
