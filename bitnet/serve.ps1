# bitnet/serve.ps1 — Windows llama-server launcher.
param(
    [int]$Port = 8081,
    [int]$Ctx = 2048,
    [int]$Threads = 0,
    [string]$ModelFile = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot   = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BitNetRoot = $env:BITNET_ROOT; if (-not $BitNetRoot) { $BitNetRoot = Join-Path $RepoRoot "bitnet\vendor" }
$ModelDir   = $env:MODEL_DIR;   if (-not $ModelDir)   { $ModelDir   = Join-Path $RepoRoot "bitnet\models" }

$ServerBin = Join-Path $BitNetRoot "build\bin\Release\llama-server.exe"
if (-not (Test-Path $ServerBin)) {
    $ServerBin = Join-Path $BitNetRoot "build\bin\llama-server.exe"
}
if (-not (Test-Path $ServerBin)) {
    Write-Error "not built. run: .\bitnet\setup.ps1"
    exit 1
}

if (-not $ModelFile) {
    $ModelFile = (Get-ChildItem -Path $ModelDir -Filter *.gguf | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
}
if (-not $ModelFile -or -not (Test-Path $ModelFile)) {
    Write-Error "no model in $ModelDir. run: .\bitnet\setup.ps1"
    exit 1
}

if ($Threads -le 0) { $Threads = [Environment]::ProcessorCount }

Write-Host "→ serving $(Split-Path -Leaf $ModelFile) on :$Port (ctx=$Ctx, threads=$Threads)"
Write-Host "  OpenAI-compatible: http://localhost:$Port/v1/chat/completions"
Write-Host "  Autoclaw: `$env:BITNET_URL='http://localhost:$Port/v1'"

& $ServerBin `
    --model $ModelFile `
    --host 0.0.0.0 `
    --port $Port `
    --ctx-size $Ctx `
    --threads $Threads `
    --n-predict 512
