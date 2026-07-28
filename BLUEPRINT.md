# Autoclaw — Blueprint

> Self-improving AI experiment loop. No-code. Karpathy-pattern. Claude/GPT/DeepSeek/local.

**Version:** 0.3.1 · **Date:** 2026-07-17 · **License:** MIT

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

## Release flow

1. Bump version in: `Cargo.toml`, `agent.go` (constant), `sdk/python/pyproject.toml`, `sdk/js/package.json`, `mobile/Cargo.toml`, `packaging/*`.
2. `git tag v0.1.0 && git push --tags` →
   - `release.yml` builds 10 binaries (5 Rust + 5 Go), creates GitHub Release.
   - `docker.yml` pushes `ghcr.io/dnzengou/autoclaw:0.1.0` + `:latest`.
   - `android.yml` attaches APK to release.
3. Manual: `pip publish`, `npm publish`, update Homebrew tap with new SHA256.

## Changelog

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

*Autoclaw v0.3.1 · MIT · Karpathy pattern · Caveman context format*
