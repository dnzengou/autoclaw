# Autoclaw — Blueprint

> Self-evolving AI experiment loop. No-code. Karpathy-pattern. Claude/GPT/DeepSeek/local.

**Version:** 0.3.0 · **Date:** 2026-07-13 · **License:** MIT

## Mission

Humans set direction in `context.md`. AI proposes hypotheses, runs experiments,
commits improvements, reverts regressions. Loop until budget exhausted.

## EvoMetaClaw — the strategic moat

Every experiment is a training signal. Strategy genomes (`evo.go`) compete via
replicator dynamics: softmax selection by fitness, EMA fitness updates from real
outcomes, auto-summarization of winning hypotheses into new genomes, and a
circuit breaker that injects diversity on stagnation. All outcomes append to
`.autoclaw/evo/trajectories.jsonl`.

Rationale: a competitor can copy a registry. They cannot copy SkillOpt-powered
self-evolving loops without rebuilding the training paradigm *and* accumulating
the trajectory data. The dataset compounds with every run — that is the flywheel.

## Deals pipeline — commercial use case

`deals.go` + the Deals dashboard tab: prospect intake (manual, webhook POST to
`/api/deals`, or explicit fetch from `AUTOCLAW_DEALS_FEED`), keyword
qualification against the desiredsolutions toolbox (Clow, SAI Agency, MOOC
Studio, ProductizeYou, Funding Dashboard, CAS Lab), auto-drafted proposals with
price estimates, then a human-gated lifecycle: qualified → approved → delivered
→ paid. Nothing leaves the system without operator approval. Payment link via
`PAYMENT_LINK_URL`.

## Architecture (production path)

- **Go binary** (`agent.go` + `evo.go` + `deals.go`, stdlib only) — the shipped
  server: experiment loop, SSE dashboard, EvoMetaClaw, deals API. No external
  Go dependencies; no CDN dependencies in the dashboard (self-contained SVG chart).
- **Rust workspace** (`src/`) — the long-term core; compiles clean (fmt, clippy
  -D warnings, build) with libgit2/prometheus-exporter dependencies removed
  (git CLI subprocess + hand-rendered Prometheus text instead).
- **Python** (`agent.py`) — reference implementation.
- LLM backends: Anthropic (`claude-opus-4-8` default, `AUTOCLAW_MODEL` to
  override), DeepSeek, OpenAI, or the built-in heuristic fallback — no LLM key
  is a hard dependency.

## Distribution channels — v0.1.0

| Channel | Audience | Install | Status |
|---|---|---|---|
| **Rust binary** (5 targets) | power users / servers | `curl autoclaw.dev/install.sh \| sh` | ✅ CI ready |
| **Go binary** (5 targets) | minimal-deps users | same install script | ✅ CI ready |
| **Docker image** (amd64+arm64) | containers / k8s | `docker run ghcr.io/dnzengou/autoclaw:latest` | ✅ GHCR workflow |
| **Python SDK + CLI** | data scientists | `pip install autoclaw` | ✅ pyproject ready |
| **JS/TS SDK** | web devs | `npm i @autoclaw/sdk` | ✅ tsup ready |
| **Go SDK** | infra/backend devs | `go get github.com/dnzengou/autoclaw/sdk/go` | ✅ module ready |
| **Android APK** | mobile | side-load or Play Store | ✅ Tauri 2 workflow |
| **iOS IPA** | mobile | TestFlight (manual) | ✅ Tauri 2 ready |
| **Homebrew** | macOS/Linux | `brew install autoclaw/tap/autoclaw` | ✅ formula ready |
| **Scoop** | Windows | `scoop install autoclaw` | ✅ manifest ready |
| **Debian .deb** | Linux | `dpkg -i autoclaw_0.1.0.deb` | ✅ control file ready |
| **Fly.io** | one-click deploy | `fly launch` | ✅ existing |
| **Railway** | one-click deploy | Deploy button | ✅ existing |
| **Render** | one-click deploy | Blueprint button | ✅ existing |

## File manifest — new in v0.1.0

```
autoclaw/
├── sdk/
│   ├── python/                 # pip install autoclaw
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   └── src/autoclaw/
│   │       ├── __init__.py
│   │       ├── client.py       # async HTTP + SSE + WS client
│   │       ├── models.py       # pydantic types
│   │       └── cli.py          # entry point: `autoclaw`
│   ├── js/                     # npm i @autoclaw/sdk
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── README.md
│   │   └── src/
│   │       ├── index.ts
│   │       ├── client.ts
│   │       └── types.ts
│   └── go/                     # go get github.com/dnzengou/autoclaw/sdk/go
│       ├── go.mod
│       ├── client.go
│       ├── types.go
│       └── README.md
├── mobile/                     # Tauri 2 mobile shell (APK + IPA)
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── build.rs
│   ├── src/{lib.rs,main.rs}
│   └── README.md
├── packaging/
│   ├── homebrew/autoclaw.rb    # brew tap formula
│   ├── scoop/autoclaw.json     # scoop manifest
│   └── debian/control          # apt/.deb metadata
├── .github/workflows/
│   ├── release.yml             # cross-platform Rust+Go binaries
│   ├── android.yml             # APK build
│   └── docker.yml              # multi-arch GHCR push
├── install.sh                  # POSIX installer (curl-pipe)
├── install.ps1                 # Windows installer
└── DISTRIBUTION.md             # consumer-facing install guide
```

## Roadmap

| Item | Status |
|---|---|
| Core agent loop (Rust + Python + Go) | ✅ |
| Git integration | ✅ |
| Web dashboard | ✅ |
| Claude / DeepSeek / OpenAI harness | ✅ |
| Multi-channel distribution | ✅ |
| EvoMetaClaw: genome selection + trajectory flywheel | ✅ |
| Deals pipeline: intake → qualify → approve → paid | ✅ |
| Dashboard v2: tabs, self-contained chart (no CDN) | ✅ |
| Rust core compiles clean (fmt + clippy + build blocking in CI) | ✅ |
| LLM-refined proposals (optional, key-gated) | 🔲 |
| Evo: GRPO-style multi-objective fitness | 🔲 |
| Multi-agent support | 🔲 |
| Plugin system | 🔲 |
| Community leaderboard | 🔲 |

## Release flow

1. Bump version in: `Cargo.toml`, `agent.go` (constant), `sdk/python/pyproject.toml`, `sdk/js/package.json`, `mobile/Cargo.toml`, `packaging/*`.
2. `git tag v0.1.0 && git push --tags` →
   - `release.yml` builds 10 binaries (5 Rust + 5 Go), creates GitHub Release.
   - `docker.yml` pushes `ghcr.io/dnzengou/autoclaw:0.1.0` + `:latest`.
   - `android.yml` attaches APK to release.
3. Manual: `pip publish`, `npm publish`, update Homebrew tap with new SHA256.

## Changelog

### 0.3.0 — 2026-07-13
- **EvoMetaClaw** (`evo.go`): strategy genomes, softmax selection, fitness from
  live outcomes, auto-skill summarization, stagnation circuit breaker, persisted
  trajectory log — the data flywheel.
- **Deals pipeline** (`deals.go`): prospect intake, toolbox qualification,
  proposal drafting, human-gated approve/deliver/paid lifecycle, optional feed
  fetch, payment-link config.
- **Dashboard v2**: three tabs (Loop / Evolution / Deals), Chart.js CDN removed
  (self-contained SVG chart), accessible status badges, SSE live updates.
- **Go hardening**: race-free loop lifecycle (mutex-guarded state), server no
  longer exits when stdin closes in containers, `--auto-start` flag, Anthropic
  model updated to `claude-opus-4-8` (env `AUTOCLAW_MODEL`), root `go.mod`.
- **Rust core fixed**: compiles clean for the first time — removed 13 unused or
  broken dependencies (incl. git2 → git CLI, metrics-exporter-prometheus →
  hand-rendered text format), real start/stop wiring in the API server, rubric
  endpoints implemented. CI gates (fmt, clippy -D warnings, test, build) now blocking.
- Trimmed junk from the repo (committed zip archive, runtime results.json).

### 0.1.0 — 2026-06-15
- Initial multi-channel distribution: Python SDK, JS SDK, Go SDK, Android APK, Homebrew, Scoop, .deb, GHCR.
- Cross-platform binary CI (Rust + Go × Linux/macOS/Windows × amd64/arm64).
- Tauri 2 mobile shell wrapping React dashboard.
- Smart install.sh / install.ps1 with SHA256 verification.

---

*Autoclaw v0.1.0 · MIT · Karpathy pattern · Caveman context format*
