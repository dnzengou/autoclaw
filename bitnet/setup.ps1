# bitnet/setup.ps1 — Windows: clone microsoft/BitNet, build (MSVC), download model.
#
# Usage:
#   .\bitnet\setup.ps1
#   .\bitnet\setup.ps1 -Model llama3-8b-1.58bit
#   .\bitnet\setup.ps1 -NoModel
#
# Requires: Git, CMake, Python 3.10+, Visual Studio 2022 Build Tools with C++ workload.

param(
    [string]$Model = "",
    [switch]$NoModel
)

$ErrorActionPreference = "Stop"

function Require-Cmd($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Error "missing: $name (install and retry)"
        exit 1
    }
}
foreach ($c in @("git", "cmake", "python", "curl")) { Require-Cmd $c }

$RepoRoot   = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BitNetRoot = $env:BITNET_ROOT; if (-not $BitNetRoot) { $BitNetRoot = Join-Path $RepoRoot "bitnet\vendor" }
$ModelDir   = $env:MODEL_DIR;   if (-not $ModelDir)   { $ModelDir   = Join-Path $RepoRoot "bitnet\models" }
$ModelsJson = Join-Path $RepoRoot "bitnet\models.json"

# ─── 1. Clone ────────────────────────────────────────────────────────────────
if (-not (Test-Path (Join-Path $BitNetRoot ".git"))) {
    Write-Host "→ cloning microsoft/BitNet …"
    git clone --recursive --depth 1 https://github.com/microsoft/BitNet $BitNetRoot
} else {
    Write-Host "→ updating microsoft/BitNet …"
    git -C $BitNetRoot pull --ff-only
    git -C $BitNetRoot submodule update --init --recursive
}

# ─── 2. Build ────────────────────────────────────────────────────────────────
$LlamaCli = Join-Path $BitNetRoot "build\bin\Release\llama-cli.exe"
if (Test-Path $LlamaCli) {
    Write-Host "→ build already present"
} else {
    Write-Host "→ configuring CMake …"
    Push-Location $BitNetRoot
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
    python setup_env.py --hf-repo microsoft/BitNet-b1.58-2B-4T-gguf --quant-type i2_s
    Pop-Location
}

# ─── 3. Download model ───────────────────────────────────────────────────────
if ($NoModel) { Write-Host "→ -NoModel set, skipping"; exit 0 }

New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

if (-not $Model) {
    $Model = (python -c "import json,sys; print(json.load(open('$($ModelsJson -replace '\\', '/')')).get('default'))").Trim()
}

$meta = python -c @"
import json
m = json.load(open('$($ModelsJson -replace '\\', '/')'))['models']['$Model']
print(m['url']); print(m['filename']); print(m['size_bytes'])
"@
$url, $filename, $size = $meta -split "`n" | ForEach-Object { $_.Trim() }
$out = Join-Path $ModelDir $filename

if ((Test-Path $out) -and ((Get-Item $out).Length -eq [int64]$size)) {
    Write-Host "→ model already present: $out"
} else {
    Write-Host "→ downloading $Model ($size bytes) …"
    curl -L --fail --progress-bar -o "$out.tmp" $url
    Move-Item -Force "$out.tmp" $out
}

Write-Host ""
Write-Host "✓ ready. Model: $out"
Write-Host "  Start server: .\bitnet\serve.ps1"
