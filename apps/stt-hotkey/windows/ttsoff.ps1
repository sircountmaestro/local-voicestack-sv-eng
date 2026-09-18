$ErrorActionPreference = "Continue"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$Stop = Join-Path $Repo "apps\stt-hotkey\scripts\stt-stop.ps1"
& $Stop

function Stop-Compose([string]$Rel) {
    $file = Join-Path $Repo $Rel
    if (Test-Path $file) {
        docker compose -f $file down
    }
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    Stop-Compose "apps\kokoro-fastapi\compose.yml"
    Stop-Compose "apps\azure-speech-gateway\compose.yml"
    Stop-Compose "apps\whisper-stt-sv\compose.yml"
}

Write-Host "TTS/STT avstängd."
