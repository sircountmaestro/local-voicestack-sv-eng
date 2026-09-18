# Starta STT-lyssnaren om den inte redan kör. Anropas från windows/tts.ps1.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}
Set-Location $Root
& $Python -m stt_hotkey ensure
exit $LASTEXITCODE
