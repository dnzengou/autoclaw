# Install Autoclaw

Pick your channel.

## CLI / Server binary

```bash
# macOS / Linux / WSL
curl -fsSL https://autoclaw.dev/install.sh | sh

# Windows (PowerShell)
iwr -useb https://autoclaw.dev/install.ps1 | iex
```

Or download from [Releases](https://github.com/dnzengou/autoclaw/releases) directly:

| Platform | Asset |
|---|---|
| Linux x86_64 | `autoclaw-x86_64-unknown-linux-gnu` |
| Linux arm64 | `autoclaw-aarch64-unknown-linux-gnu` |
| macOS Intel | `autoclaw-x86_64-apple-darwin` |
| macOS Apple Silicon | `autoclaw-aarch64-apple-darwin` |
| Windows | `autoclaw-x86_64-pc-windows-msvc.exe` |

Each asset is paired with a `.sha256` file. The installer verifies it; do likewise manually.

## Package managers

```bash
# Homebrew
brew install autoclaw/tap/autoclaw

# Scoop (Windows)
scoop bucket add autoclaw https://github.com/autoclaw/scoop-bucket
scoop install autoclaw

# Debian / Ubuntu
curl -fsSL https://autoclaw.dev/deb/autoclaw_0.1.0_amd64.deb -o autoclaw.deb
sudo dpkg -i autoclaw.deb

# Arch (AUR) — community-maintained
yay -S autoclaw-bin
```

## Docker

```bash
docker run -p 8080:8080 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v "$PWD":/work \
  ghcr.io/dnzengou/autoclaw:latest
```

Multi-arch image — works on `linux/amd64` and `linux/arm64` (incl. Apple Silicon Docker).

## SDKs

```bash
# Python
pip install autoclaw

# JavaScript / TypeScript
npm i @autoclaw/sdk          # or pnpm/yarn/bun

# Go
go get github.com/dnzengou/autoclaw/sdk/go

# Rust (use the binary's REST API directly — native crate planned for v0.2)
```

## Mobile

| Platform | Download |
|---|---|
| Android | APK on [Releases](https://github.com/dnzengou/autoclaw/releases) or build with `cargo tauri android build` |
| iOS | `cargo tauri ios build` then sideload via TestFlight |

The mobile shell connects to a running Autoclaw server. Run the server anywhere reachable
(your laptop on LAN, a VPS, Fly.io, Railway), then point the app at it.

## One-click cloud deploys

| Provider | Command |
|---|---|
| Fly.io | `fly launch` (uses `fly.toml`) |
| Railway | "Deploy on Railway" button (uses `railway.json`) |
| Render | "Deploy to Render" button (uses `render.yaml`) |
| Cloud Run | `gcloud run deploy --image ghcr.io/dnzengou/autoclaw:latest` |

## From source

```bash
git clone https://github.com/dnzengou/autoclaw
cd autoclaw

# Rust core
cargo build --release && ./target/release/autoclaw --help

# Go variant
go build -o autoclaw-go agent.go && ./autoclaw-go

# Python harness
python agent.py
```
