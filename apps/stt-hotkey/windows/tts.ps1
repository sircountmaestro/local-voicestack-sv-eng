# Windows-motsvarighet till bin/tts
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$env:TTSPRO_ROOT = $Repo
$Ensure = Join-Path $Repo "apps\stt-hotkey\scripts\stt-ensure.ps1"

& $Ensure

function Start-Compose([string]$Rel) {
    $file = Join-Path $Repo $Rel
    if (Test-Path $file) {
        docker compose -f $file up -d
    }
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    Start-Compose "apps\kokoro-fastapi\compose.yml"
    Start-Compose "apps\azure-speech-gateway\compose.yml"
}

Write-Host "Stoppa med: ttsoff"
