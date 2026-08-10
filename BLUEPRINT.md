# Autoclaw — Blueprint

> Self-improving AI experiment loop **and** private AI operating system.
> No-code. Karpathy-pattern. Claude/GPT/DeepSeek/local/BitNet. Six-layer OS on-device.

**Version:** 0.6.0 · **Date:** 2026-08-10 · **License:** MIT

## Mission

Humans set direction in `context.md`. AI proposes hypotheses, runs experiments,
commits improvements, reverts regressions. Loop until budget exhausted.

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
| **Docker (BitNet edition)** | privacy / air-gapped / regulated | `docker build -f Dockerfile.bitnet -t autoclaw:bitnet .` | ✅ v0.5 |
| **Voice agent (offline)** | kiosk / field ops / accessibility | `./voice/setup.sh && ./voice/ask.sh` | ✅ v0.5 |

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
| Multi-agent support | 🔲 |
| Plugin system | 🔲 |
| Distributed training | 🔲 |
| Community leaderboard | 🔲 |

## Design system — v0.3

One visual language across three surfaces: the landing (`site/index.html`), the standalone
dashboard served by the Go / Rust / Python variants (`dashboard.html`), and the React shell
that Tauri bundles for mobile (`ui/`). Same tokens, same components — replace any and the
other two update by convention.

### Tokens

```
--bg           #0b0d10      surface base           --font-sans   ui-sans-serif …
--surface      #14181d      panel                  --font-mono   ui-monospace …
--surface-2    #1a1f26      panel-inside / hover   --radius      8px
--border       #232a33      thin dividers          --shadow-panel  inset highlight
--border-hi    #2f3844      hover state
--fg           #eef2f7      text
--muted        #8a94a3      secondary text
--accent       #ff7a3d      brand orange · CTAs
--accent-2     #ffd166      brand gold  · score line, best-run marker
--ok           #2dd4a8      status: completed
--warn         #f0b429      status: reverted
--danger       #ef4444      status: failed / disconnected
```

Palette validated via dataviz `scripts/validate_palette.js` — one hue for the score
sparkline (single series → no legend, panel title names it), semantic status colors
paired with text labels for CVD safety.

### Principles

1. **Less chrome, more data.** No card shadows, no gradients on data. One 1 px border,
   flat backgrounds, monospace numerals, tabular-nums for alignment.
2. **Live is a state, not a page.** SSE pulse in the topbar; the Live tab keeps the
   headline stats + sparkline visible while experiments stream in.
3. **Keyboard-first.** `1` `2` `3` switch tabs · `S` start · `X` stop · `R` reset.
   Every button shows its `<kbd>` hint inline.
4. **One tab per task.** Live (what's happening now) · History (all runs) · Context (goals).
   No submenu, no drawer, no modal.
5. **No client-side chart lib.** Score history is a 20-line inline SVG polyline. Zero
   dependency, zero flash-of-empty-chart, ~1 KB minified in the HTML page.
6. **Design belongs in CSS variables, never inline.** One theme file per surface,
   both surfaces read the same 8-value palette.

### Competitor benchmarks

| Product | What we borrowed |
|---|---|
| Linear | Topbar density, `<kbd>` hints inline with buttons, mono numerals |
| Vercel | Panel-with-uppercase-label header, hover-row tables, subtle backdrop-blur topbar |
| Aim (aimstack) | Single-hue sparkline for score history; no per-point labels |
| Cursor | Pulse dot for live-connection state |
| Weights & Biases | Comparison table with fixed column order (ID · hypothesis · score · status · dur · git) |

Explicitly NOT borrowed: colored bar charts per metric (Neptune), theme picker
(Comet), sidebar navigation (MLflow) — none earn their pixels for this tool's job.

### Surfaces

| File | Purpose | Build |
|---|---|---|
| `site/index.html` | Marketing landing at `autoclaw.dev` | Static, deploy via `vercel --prod site/` |
| `dashboard.html` | Server-fallback dashboard (all runtimes serve it) | None — single file |
| `ui/src/App.tsx` + `App.css` | React shell for the Tauri mobile app | `cd ui && npm run build` |

The React shell and `dashboard.html` render the same UI from the same tokens. Deleting
either does not affect the other; both talk to the same `/api/*` and `/events` surface.

### Trim log — v0.3 (2026-07-17)

- Deleted `ui/src/components/{Chart,ContextEditor,ExperimentList,MetricsCard}.{tsx,css}` (8 files)
- Deleted `ui/src/hooks/useWebSocket.ts` (endpoint was wrong — server exposes SSE not WS)
- Removed npm deps: `lucide-react`, `recharts`, `ws`, `react-router-dom`
- Replaced Chart.js CDN (dashboard.html) with inline SVG sparkline
- Consolidated: React UI went from 1314 lines / 10 files → 435 lines / 3 files
- Wired both surfaces to real endpoints (`/api/status`, `/api/results`, `/api/context`, `/events`)
- Added keyboard shortcuts + SSE pulse + status pills

## Demo — v0.3.1

`autoclaw.dev/demo` (or `dashboard.html?demo=1`) is a **zero-install, zero-server** trial
of the product. Same UI as the real dashboard; the difference is the data path:

- `?demo=1` short-circuits every `fetch()` call.
- Hydrates from a 20-experiment seed with a plausible F1 curve (0.72 → ~0.91, 3 reverts).
- `S` = Start simulates a live SSE stream (one new experiment every ~4 s, budget 300 s).
- `X` = Stop halts the timer. `R` = Reset returns to the seed.
- Context editor is writable but local-only.
- Amber `▶ DEMO MODE` banner links back to Install.

**Why this over a hosted `demo.autoclaw.dev`:**
- Zero infra to keep running (no VPS, no rate limits, no LLM key drain).
- Works on airplane, in restricted networks, behind corporate proxies.
- Deploys as pure static assets alongside the marketing landing.
- Same asset served at `/demo` (via `vercel.json` rewrite) and `?demo=1`.

**ARM at the funnel top:**
- Adoption: cuts time-to-first-experience from "install + LLM key + budget" to **~15 s**.
- Retention: the same UI they'll get post-install → familiarity carries over.
- Monetization: the CTA back to Install/Pro sits inside the demo, in view during the "aha".

**Follow-ups (not blocking):**
- Optional hosted `demo.autoclaw.dev` on Fly.io with rate-limited real LLM calls — nice-to-have, not required.
- Guided-tour overlay (arrows pointing at score sparkline, then experiments table, then context) — punt until we see funnel drop-offs in Plausible.

## Iterative refinement loop — v0.4 (Python prototype)

Before v0.4 the loop was flat — each iteration asked the LLM for N *new* hypotheses,
ran each one *once*, and moved on. A promising-but-imperfect hypothesis never got a
second pass; a near-miss was thrown out instead of nudged.

v0.4 adds an AlphaGo / MCTS-style **Run → Evaluate → Improve → Run again** chain around
`run_experiment()`. After each fresh hypothesis runs, the agent decides whether to
*refine* that branch (change 1–2 params, keep the rest) or move on to a new one.

### The selective policy

Refine only when the branch is worth expanding:

- Skip if `status == failed` (crashed — refinement is premature).
- Skip if `status == reverted` (git rolled back — parent params no longer on disk).
- Skip if `score < best_score - refinement_gap` (dead branch — burn budget elsewhere).
- Skip if `budget_remaining <= min_refinement_budget` (no time for another train).
- Otherwise refine, up to `max_refinement_depth` times per branch.

Inside a chain, stop early on: target reached, score plateau, or LLM decline.

### The critique-and-refine prompt

The LLM sees the parent's hypothesis, params, metrics, and score, plus the rubric.
It returns exactly:

```json
{"critique": "...", "refinement_strategy": "...", "params": { ... }}
```

Written back into `results.json` alongside the standard fields, so lineage is
inspectable end-to-end. A heuristic fallback perturbs the highest-magnitude numeric
param by ±20% when no LLM key is set — enough to smoke-test the wiring.

### New CLI flags

| Flag | Default | Purpose |
|---|---|---|
| `--max-refinement-depth` | `3` | Cap the chain per branch (0 disables) |
| `--plateau-tolerance` | `0.005` | Stop when \|Δscore\| < this |
| `--target-score` | `1.0` | Stop chain once reached |
| `--refinement-gap` | `0.03` | Only refine if `score >= best_score - gap` |
| `--min-refinement-budget` | `5.0` | Seconds below which refinement is skipped |
| `--refinement-model` | — | Optional cheaper model just for critique |

### New optional result fields (elided when null/zero)

- `parent_id: str` — ID of the experiment being refined
- `refinement_depth: int` — 0 for fresh, 1..N for refinements
- `critique: str` — LLM's read on why the parent scored what it did
- `refinement_strategy: str` — one-line rationale for the change

Dashboard is unaffected — unknown properties are ignored by the SSE handler.
Lineage rendering (indent + hover critique) is deferred until the pattern
proves itself. Go and Rust ports follow after Python validation.

## Release flow

1. Bump version in: `Cargo.toml`, `agent.go` (constant), `sdk/python/pyproject.toml`, `sdk/js/package.json`, `mobile/Cargo.toml`, `packaging/*`.
2. `git tag v0.1.0 && git push --tags` →
   - `release.yml` builds 10 binaries (5 Rust + 5 Go), creates GitHub Release.
   - `docker.yml` pushes `ghcr.io/dnzengou/autoclaw:0.1.0` + `:latest`.
   - `android.yml` attaches APK to release.
3. Manual: `pip publish`, `npm publish`, update Homebrew tap with new SHA256.

## Private AI OS — v0.6 (2026-08-10)

Assembles the "Private AI OS" thesis from the top-ROI opportunities strategy: a
six-layer stack that turns BitNet from an inference engine into an operating
layer over user data. Nothing new below the runtime layer — every added byte
runs local, on CPU, stdlib-first.

### Six layers

| Layer | Directory | What it adds |
|---|---|---|
| 1 · Runtime | `bitnet/` | (v0.5) LLM inference; `BITNET_URL` env var |
| 2 · Memory | `memory/` | SQLite personal + session (rolling summary) + org memory |
| 3 · Knowledge | `rag/` | Embedding model (nomic/bge/e5) + SQLite vector store + ingest/query CLI + HTTP |
| 4 · Agents | `agents/` | Orchestrator with plan → validate → **approve** → execute → audit; research + ops agents |
| 5 · Connectors | `connectors/` | Email IMAP (r/o) + web fetch; github via `gh` CLI |
| 6 · Governance | `agents/policies.yaml` + `agents/audit.py` | Allow/approve/deny rules; JSONL audit sink SIEM-ready |

### ROI crosswalk (from the strategy doc)

| Doc's top-ROI category | Score | Autoclaw feature |
|---|---|---|
| 1. Personal & Enterprise AI OS | 10/10 | The whole stack (`autoclaw_os.py`) |
| 2. Offline AI for Edge Devices | 9.8/10 | `Dockerfile.bitnet` + `Dockerfile.aios` (air-gap via `docker save`); mobile via Tauri |
| 3. Knowledge Search / RAG / Digital Memory | 9.5/10 | `rag/` + `memory/` |
| 4. Voice-First AI Agents | 9/10 | `voice/` (v0.5) |

### Unified CLI — `autoclaw_os.py`

```
autoclaw-os status                        # what's up across all six layers
autoclaw-os ingest <path>                 # add docs to the RAG store
autoclaw-os memory add personal K V       # personal / session / org memory
autoclaw-os research "<question>"         # RAG-cited answer (read-only)
autoclaw-os ops     "<task>"              # multi-step with approvals
autoclaw-os chat    "<request>"           # free-form; LLM picks a tool
autoclaw-os serve                         # start BitNet + RAG + agent HTTP together
```

### The approval model

`agents/orchestrator.py` runs a five-step loop on every action:

```
plan (LLM proposes tool + args)
  → validate (against policies.yaml — deny / approve / auto)
    → approve (user prompt for approval-bucket tools; auto-approve flag exists for CI)
      → execute (dispatch through tools.py registry)
        → audit (append JSONL: agent, tool, args, decision, exit code, sha256(stdout))
```

Every action, every input, every decision → `~/.autoclaw/audit.jsonl` (or
`AUTOCLAW_AUDIT_LOG`). SIEM-ready format. Nothing sensitive leaves the machine
without an explicit `y` prompt or auto-approve flag.

### Files added in v0.6

```
rag/{models.json,setup.sh,serve.sh,store.py,ingest.py,query.py,server.py,README.md}   # Layer 3
memory/{schema.sql,manager.py,README.md}                                              # Layer 2
agents/{policies.yaml,tools.py,audit.py,orchestrator.py,research_agent.py,ops_agent.py,README.md,__init__.py}  # Layer 4 + 6
connectors/{email_imap.py,web_fetch.py,README.md,__init__.py}                         # Layer 5
autoclaw_os.py                                                                        # unified CLI
Dockerfile.aios                                                                       # AI OS edition — all layers baked in
docs/PRIVATE_AI_OS.md                                                                 # the 6-layer story + ROI crosswalk + industry-fit matrix
```

### Docker AI OS edition

`Dockerfile.aios` — everything in one image. Runs BitNet on :8081, RAG
embeddings on :8082, agent HTTP on :8083, dashboard on :8080. Mount `/data`
for persistent state. Supports `docker save` → USB → air-gap load.

### Business model context (from the strategy doc)

| Segment | Pricing | Shape |
|---|---|---|
| Consumer | €10–30/mo | Brew install; user's laptop |
| SMB | €20–100/user/mo | Docker on office mini-PC or shared VM |
| Enterprise | €100k–5M annual | Air-gapped Docker + K8s; SIEM; SSO; custom connectors; SLA |

v0.6 ships the technical foundation for all three tiers.

## BitNet local backend — v0.5 (2026-08-10)

Adds a **fully-offline LLM path** — no cloud, no API keys, no data egress. Wraps
Microsoft's [BitNet.cpp](https://github.com/microsoft/BitNet) (1.58-bit ternary
inference) as a drop-in local backend for `agent.py::call_llm()`.

### The privacy path

Backend precedence in `call_llm()` now:
1. `BITNET_URL` → local BitNet server (this feature)
2. `LOCAL_LLM_URL` → any OpenAI-compatible endpoint (LM Studio, Ollama, vLLM)
3. `ANTHROPIC_API_KEY` → Claude
4. `OPENAI_API_KEY` → GPT
5. Heuristic fallback (no keys, no server)

Setting `BITNET_URL=http://localhost:8081/v1` routes every hypothesis / critique /
refinement call through the local model. Nothing leaves the machine.

### Voice agent

`voice/` bundles whisper.cpp (STT) + BitNet (reasoning) + Piper (TTS) into a
fully-offline voice pipeline: `voice/ask.sh` for one-shot, `voice/agent.py
--continuous` for a listening loop. Latency ~2–4 s/turn on a laptop CPU.

### Low-hanging-fruit use cases

The privacy backend unlocks markets the cloud path can't serve: HR/legal/health
document Q&A (GDPR/HIPAA), field-ops voice assistants (offline), air-gapped SOC
enrichment, kiosk assistants, and autoclaw experiment loops for regulated ML. See
[docs/BITNET.md](docs/BITNET.md) for the full matrix.

### Install channels

| Channel | Command | Notes |
|---|---|---|
| Homebrew | `brew install autoclaw && autoclaw install-bitnet` | macOS/Linux |
| Scoop | `scoop install autoclaw && autoclaw install-bitnet` | Windows |
| .deb | `dpkg -i autoclaw_amd64.deb && autoclaw install-bitnet` | Debian/Ubuntu |
| curl-pipe | `curl … install.sh \| sh -s -- --with-bitnet` | Anywhere |
| Docker | `docker build -f Dockerfile.bitnet -t autoclaw:bitnet .` | Model baked in, ~2 GB |
| Termux | `./bitnet/setup.sh` inside Termux | Android on-device |

### Service units

- `bitnet/systemd/autoclaw-bitnet.service` — Linux (hardened: NoNewPrivileges, ProtectSystem, MemoryMax=8G)
- `bitnet/launchd/dev.autoclaw.bitnet.plist` — macOS
- `bitnet/windows/install-service.ps1` — Windows via NSSM

### Files added

```
bitnet/
├── README.md                # quick start
├── models.json              # 3 model variants (2B / 7B / 8B) with SHA256 sums
├── setup.sh / setup.ps1     # clone, cmake build, download model
├── serve.sh / serve.ps1     # llama-server on :8081 (OpenAI-compatible)
├── benchmark.sh             # tok/s sanity check
├── systemd/
├── launchd/
└── windows/
voice/
├── README.md
├── models.json              # whisper tiny.en + piper en_US-amy
├── setup.sh                 # whisper.cpp + piper + models
├── ask.sh                   # one-shot voice turn
└── agent.py                 # continuous mode + CLI
docs/
└── BITNET.md                # install matrix + use case matrix + ops runbook
Dockerfile.bitnet            # privacy edition (autoclaw + BitNet + model)
```

## Evolutionary strategy + deals pipeline — v0.4.1 (2026-08-10)

Cherry-picked from PR #31 (evometaclaw). Two novel Go modules that compose with
the v0.4 refinement loop without touching it.

- **`evo.go`** — EvoEngine: population of `SkillGenome` structs competing via
  replicator dynamics (softmax at temperature 0.25, EMA fitness at 0.8 weight).
  Seeded with 5 exploration niches (hyperparameters, regularization, architecture,
  data, exploration). Circuit breaker injects diversity when population stagnates
  more than 8 experiments. Trajectories persisted to `.autoclaw/evo/*.jsonl`.
  Stdlib only.
- **`deals.go`** — DealsEngine: prospect → qualify → propose → **human approval** →
  deliver → paid. Every outbound action gated on explicit human transition. 6
  toolbox items seeded (Clow, SAI Agency, MOOC Studio, ProductizeYou, Funding
  Dashboard, CAS Lab). State in `.autoclaw/deals.json`. Stdlib only.
- **`go.mod`** — bare module so local `go build` works without the Dockerfile's
  `go mod init` step.

Not merging PR #31 whole: it also rewrote the dashboard + gutted Cargo deps +
simplified Rust server — all predating v0.3/v0.4 and would revert shipped work.

## Changelog

### 0.6.0 — 2026-08-10
- Private AI OS thesis assembled from the top-ROI opportunities strategy doc.
- Layer 2 (Memory): `memory/` — SQLite personal + session (rolling summary) +
  org (versioned) memory. Stdlib only. CLI + Python API.
- Layer 3 (Knowledge): `rag/` — embedding models (nomic-embed-text-v1.5 /
  bge-small-en-v1.5 / multilingual-e5-large), SQLite vector store (stdlib +
  numpy), ingest CLI (txt/md/pdf/docx/code), query CLI with citations, HTTP
  wrapper. `llama-server --embedding` reuses the BitNet binary.
- Layer 4 (Agents): `agents/` — orchestrator with plan→validate→**approve**
  →execute→audit loop, research_agent (RAG-cited), ops_agent (multi-step
  planner with approval gates), policies.yaml (deny/approve/auto), tools
  registry, JSONL audit sink SIEM-ready.
- Layer 5 (Connectors): `connectors/` — email IMAP (read-only), web fetch
  (stdlib HTML→text, private-IP denylisted). github via `gh` CLI in
  `agents/tools.py` — no OAuth setup.
- `autoclaw_os.py` — unified CLI: `status | ingest | research | ops | chat |
  memory | serve`.
- `Dockerfile.aios` — Private AI OS edition. All layers baked in. Mount /data
  for persistent state. Air-gap deployable via `docker save`.
- `docs/PRIVATE_AI_OS.md` — the 6-layer story, ROI crosswalk from the strategy
  doc, industry-fit matrix, business-model tiers, roadmap.
- `install.sh` — `--with-ai-os` flag (extends `--with-bitnet` with RAG model).

### 0.5.0 — 2026-08-10
- Local BitNet.cpp backend (`bitnet/` — 1.58-bit inference, no cloud, no keys).
- Voice agent (`voice/` — whisper.cpp + BitNet + Piper, offline pipeline).
- `agent.py::call_llm()` new `BITNET_URL` + `LOCAL_LLM_URL` precedence; new
  `_call_openai_compat()` helper (OpenAI-compatible drop-in).
- `Dockerfile.bitnet` privacy edition with model baked in.
- Service units: systemd (hardened), launchd, NSSM.
- `docs/BITNET.md` — install matrix (macOS/Windows/Linux/Docker/Android/iOS),
  10 low-hanging-fruit use cases, ops runbook.
- Branch cleanup: merged 9 safe dependabot PRs; closed 8 stale/major-version PRs;
  cherry-picked evo.go + deals.go from #31 as PR #34.

### 0.4.1 — 2026-08-10
- Cherry-picked `evo.go` (EvoEngine — replicator dynamics + circuit breaker) and
  `deals.go` (DealsEngine — human-approval-gated pipeline) from PR #31, plus
  `go.mod`. See "Evolutionary strategy + deals pipeline" above.

### 0.4.0 — 2026-07-24
- Iterative refinement loop (Python prototype in `agent.py`): after each fresh hypothesis,
  the agent selectively refines promising branches — AlphaGo / MCTS-style expansion
  instead of pure breadth-first random search.
- New `refine_experiment()` + policy gate `_should_refine()` + heuristic fallback for
  no-LLM smoke testing.
- Results grow four optional lineage fields (`parent_id`, `refinement_depth`, `critique`,
  `refinement_strategy`) — all `omitempty`-style so existing consumers stay unchanged.
- New CLI flags: `--max-refinement-depth`, `--plateau-tolerance`, `--target-score`,
  `--refinement-gap`, `--min-refinement-budget`, `--refinement-model`.
- Go + Rust ports of the pattern deferred to a follow-up.

### 0.3.1 — 2026-07-17
- User demo: `dashboard.html?demo=1` / `autoclaw.dev/demo` — same UI, seeded data + simulated SSE, zero server.
- Landing hero adds primary `▶ Try the demo` CTA before Install. `cta-hint` copy quantifies time-to-first-experience (~15 s).
- Vercel rewrite `/demo → /dashboard.html?demo=1`; sitemap entry priority 0.95.

### 0.3.0 — 2026-07-17
- Unified visual language across three surfaces (landing, dashboard.html, React shell).
- Design tokens documented; palette validated for CVD safety and contrast.
- React UI: 1314 lines / 10 files → 435 lines / 3 files. Deleted 4 component pairs + hook, dropped 4 npm deps.
- Fixed broken endpoints in React shell: `/api/experiments` → `/api/results`, WS `/ws` → SSE `/events`.
- Standalone `dashboard.html` rewritten to match tokens; replaced Chart.js CDN with inline SVG sparkline.
- Keyboard shortcuts (`1`/`2`/`3` tabs, `S`/`X`/`R` control) + SSE pulse + status pills.

### 0.2.0 — 2026-06-18
- CI honesty (no `continue-on-error` as a strategy), post-release manifest automation,
  security defaults (Dependabot × 9 ecosystems, CodeQL, SECURITY.md), SDK smoke tests,
  container hardening (Go-based image, non-root, tini, alpine), Tauri app icons.

### 0.1.0 — 2026-06-15
- Initial multi-channel distribution: Python SDK, JS SDK, Go SDK, Android APK, Homebrew, Scoop, .deb, GHCR.
- Cross-platform binary CI (Rust + Go × Linux/macOS/Windows × amd64/arm64).
- Tauri 2 mobile shell wrapping React dashboard.
- Smart install.sh / install.ps1 with SHA256 verification.

---

*Autoclaw v0.4.0 · MIT · Karpathy pattern · Caveman context format*
