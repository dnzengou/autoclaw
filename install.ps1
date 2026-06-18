# Autoclaw installer for Windows.
# Usage:
#   iwr -useb https://autoclaw.dev/install.ps1 | iex
#
# Env overrides: AUTOCLAW_VERSION, AUTOCLAW_PREFIX, AUTOCLAW_REPO

$ErrorActionPreference = "Stop"

$repo    = $env:AUTOCLAW_REPO    ?? "dnzengou/autoclaw"
$version = $env:AUTOCLAW_VERSION ?? "latest"
$prefix  = $env:AUTOCLAW_PREFIX  ?? "$env:LOCALAPPDATA\autoclaw\bin"

function Log($m) { Write-Host "[autoclaw] $m" }

# Detect arch
$arch = if ([System.Environment]::Is64BitOperatingSystem) { "x86_64" } else { throw "32-bit unsupported" }
$target = "$arch-pc-windows-msvc"
$binary = "autoclaw-$target.exe"

# Resolve version
if ($version -eq "latest") {
  $rel = Invoke-RestMethod "https://api.github.com/repos/$repo/releases/latest"
  $version = $rel.tag_name
}
Log "Installing autoclaw $version for $target"

# Download
$tmp = New-Item -ItemType Directory -Path "$env:TEMP\autoclaw-$([guid]::NewGuid())"
try {
  $url  = "https://github.com/$repo/releases/download/$version/$binary"
  $hash = "$url.sha256"
  Invoke-WebRequest $url  -OutFile "$tmp\$binary"
  Invoke-WebRequest $hash -OutFile "$tmp\$binary.sha256"

  # Verify
  $expected = (Get-Content "$tmp\$binary.sha256").Split(' ')[0]
  $actual   = (Get-FileHash "$tmp\$binary" -Algorithm SHA256).Hash.ToLower()
  if ($expected -ne $actual) { throw "checksum mismatch" }

  # Install
  New-Item -ItemType Directory -Force -Path $prefix | Out-Null
  $dest = Join-Path $prefix "autoclaw.exe"
  Move-Item -Force "$tmp\$binary" $dest

  # PATH
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if ($userPath -notlike "*$prefix*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$prefix", "User")
    Log "Added $prefix to PATH (restart shell to pick up)"
  }

  Log "Installed: $dest"
  Log "Next: autoclaw init my-project"
} finally {
  Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
