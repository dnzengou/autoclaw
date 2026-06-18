# Autoclaw — Blueprint

> Self-improving AI experiment loop. No-code. Karpathy-pattern. Claude/GPT/DeepSeek/local.

**Version:** 0.1.0 · **Date:** 2026-06-15 · **License:** MIT

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

## Release flow

1. Bump version in: `Cargo.toml`, `agent.go` (constant), `sdk/python/pyproject.toml`, `sdk/js/package.json`, `mobile/Cargo.toml`, `packaging/*`.
2. `git tag v0.1.0 && git push --tags` →
   - `release.yml` builds 10 binaries (5 Rust + 5 Go), creates GitHub Release.
   - `docker.yml` pushes `ghcr.io/dnzengou/autoclaw:0.1.0` + `:latest`.
   - `android.yml` attaches APK to release.
3. Manual: `pip publish`, `npm publish`, update Homebrew tap with new SHA256.

## Changelog

### 0.1.0 — 2026-06-15
- Initial multi-channel distribution: Python SDK, JS SDK, Go SDK, Android APK, Homebrew, Scoop, .deb, GHCR.
- Cross-platform binary CI (Rust + Go × Linux/macOS/Windows × amd64/arm64).
- Tauri 2 mobile shell wrapping React dashboard.
- Smart install.sh / install.ps1 with SHA256 verification.

---

*Autoclaw v0.1.0 · MIT · Karpathy pattern · Caveman context format*
