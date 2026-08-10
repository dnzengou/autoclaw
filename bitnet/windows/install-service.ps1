# bitnet/windows/install-service.ps1
# Register the BitNet server as a Windows Service via NSSM.
#
# Prereqs:
#   - Run as Administrator
#   - NSSM installed (choco install nssm  OR  scoop install nssm)
#   - .\bitnet\setup.ps1 already run

param(
    [string]$ServiceName = "AutoclawBitNet",
    [int]$Port = 8081,
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $InstallDir) {
    $InstallDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$NssmPath = (Get-Command nssm -ErrorAction SilentlyContinue).Source
if (-not $NssmPath) {
    Write-Error "nssm not found. Install with: scoop install nssm  (or choco install nssm)"
    exit 1
}

$ServeScript = Join-Path $InstallDir "bitnet\serve.ps1"
if (-not (Test-Path $ServeScript)) {
    Write-Error "serve.ps1 not found at $ServeScript. Run bitnet\setup.ps1 first."
    exit 1
}

# Remove existing service if present
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "→ removing existing service $ServiceName"
    & $NssmPath stop $ServiceName confirm | Out-Null
    & $NssmPath remove $ServiceName confirm | Out-Null
}

Write-Host "→ installing $ServiceName"
& $NssmPath install $ServiceName "powershell.exe" `
    "-NoProfile -ExecutionPolicy Bypass -File `"$ServeScript`" -Port $Port"

& $NssmPath set $ServiceName AppDirectory $InstallDir
& $NssmPath set $ServiceName AppEnvironmentExtra "BITNET_PORT=$Port"
& $NssmPath set $ServiceName Start SERVICE_AUTO_START
& $NssmPath set $ServiceName AppStdout (Join-Path $InstallDir "bitnet\bitnet.log")
& $NssmPath set $ServiceName AppStderr (Join-Path $InstallDir "bitnet\bitnet.err")
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateBytes 10485760

Write-Host "→ starting $ServiceName"
& $NssmPath start $ServiceName

Write-Host ""
Write-Host "✓ $ServiceName installed on port $Port"
Write-Host "  logs:   $InstallDir\bitnet\bitnet.log"
Write-Host "  status: Get-Service $ServiceName"
Write-Host "  stop:   Stop-Service $ServiceName"
Write-Host "  remove: nssm remove $ServiceName confirm"
