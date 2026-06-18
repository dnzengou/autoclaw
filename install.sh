#!/usr/bin/env sh
# Autoclaw installer — detects OS/arch, fetches release binary, verifies SHA256.
# Usage: curl -fsSL https://autoclaw.dev/install.sh | sh

set -eu

REPO="${AUTOCALW_REPO:-dnzengou/autoclaw}"
VERSION="${AUTOCALW_VERSION:-latest}"
PREFIX="${AUTOCALW_PREFIX:-/usr/local/bin}"

log() { printf '[autoclaw] %s\n' "$*"; }
die() { printf '[autoclaw] error: %s\n' "$*" >&2; exit 1; }

# ─── Detect platform ────────────────────────────────────────────────────────
os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m)"

case "$os" in
  linux)  os_tag="unknown-linux-gnu" ;;
  darwin) os_tag="apple-darwin" ;;
  msys*|cygwin*|mingw*) os_tag="pc-windows-msvc"; ext=".exe" ;;
  *) die "unsupported OS: $os" ;;
esac

case "$arch" in
  x86_64|amd64)   arch_tag="x86_64" ;;
  aarch64|arm64)  arch_tag="aarch64" ;;
  *) die "unsupported arch: $arch" ;;
esac

target="${arch_tag}-${os_tag}"
ext="${ext:-}"
binary="autoclaw-${target}${ext}"

# ─── Resolve version ────────────────────────────────────────────────────────
if [ "$VERSION" = "latest" ]; then
  VERSION="$(
    curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" |
      sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n1
  )"
  [ -n "$VERSION" ] || die "could not resolve latest version"
fi

log "Installing autoclaw $VERSION for $target"

# ─── Download ───────────────────────────────────────────────────────────────
url_base="https://github.com/${REPO}/releases/download/${VERSION}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

curl -fsSL "$url_base/$binary"        -o "$tmp/$binary"
curl -fsSL "$url_base/$binary.sha256" -o "$tmp/$binary.sha256"

# ─── Verify ─────────────────────────────────────────────────────────────────
cd "$tmp"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum -c "$binary.sha256" || die "checksum mismatch — aborting"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 -c "$binary.sha256" || die "checksum mismatch — aborting"
else
  log "warning: no sha256 tool found, skipping checksum verification"
fi

# ─── Install ────────────────────────────────────────────────────────────────
chmod +x "$binary"
target_path="$PREFIX/autoclaw${ext}"

if [ -w "$PREFIX" ]; then
  mv "$binary" "$target_path"
else
  log "Installing to $PREFIX (sudo required)"
  sudo mv "$binary" "$target_path"
fi

log "Installed: $target_path"
"$target_path" --version 2>/dev/null || true
log "Next: autoclaw init my-project"
