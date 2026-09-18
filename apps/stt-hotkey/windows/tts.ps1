# Starta stacken på Windows. Anropas av tts.cmd / tts.ps1 på PATH.
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$env:TTSPRO_ROOT = $Repo

$Ensure = Join-Path $Repo "apps\stt-hotkey\scripts\stt-ensure.ps1"
if (Test-Path $Ensure) { & $Ensure }

function Start-Compose([string]$Rel) {
    $file = Join-Path $Repo $Rel
    if (Test-Path $file) { docker compose -f $file up -d }
}

$gpu = $false
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    & nvidia-smi -L 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $gpu = $true }
}
if ($gpu) {
    Start-Compose "apps\kokoro-fastapi\compose.yml"
} else {
    Start-Compose "apps\kokoro-fastapi\compose.cpu.yml"
}

$azureEnv = Join-Path $Repo "apps\azure-speech-gateway\.env"
$hasKey = $false
if (Test-Path $azureEnv) {
    $hasKey = Select-String -Path $azureEnv -Pattern '^AZURE_SPEECH_KEY=\S+' -Quiet
}
if ($hasKey) {
    Start-Compose "apps\azure-speech-gateway\compose.yml"
} else {
    Write-Host "Azure hoppas över (ingen nyckel). Se README.md."
}

Start-Compose "apps\whisper-stt-sv\compose.yml"
Write-Host "Stoppa med ttsoff.cmd eller ttsoff.ps1"
