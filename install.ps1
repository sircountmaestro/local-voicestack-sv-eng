# Installation på en ny Windows-dator. Ingen Azure-nyckel medföljer.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "== local-voicestack-sv-eng install $Root =="

function Test-Cmd($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Cmd "docker")) { Write-Warning "Installera Docker Desktop." }
if (-not (Test-Cmd "python")) { Write-Warning "Installera Python 3.12+ och bocka i Add to PATH." }
if (-not (Test-Cmd "ffmpeg")) { Write-Warning "Installera FFmpeg och lägg det på PATH." }
if (-not (Test-Cmd "git")) { Write-Warning "Installera Git for Windows (ger Git Bash)." }

$AzureEnv = Join-Path $Root "apps\azure-speech-gateway\.env"
$AzureEx = Join-Path $Root "apps\azure-speech-gateway\.env.example"
if (-not (Test-Path $AzureEnv)) {
    Copy-Item $AzureEx $AzureEnv
    Write-Host "Skapade tom azure .env — ingen nyckel i git. Se README.md."
}
$WhisperEnv = Join-Path $Root "apps\whisper-stt-sv\.env"
$WhisperEx = Join-Path $Root "apps\whisper-stt-sv\.env.example"
if (-not (Test-Path $WhisperEnv)) {
    Copy-Item $WhisperEx $WhisperEnv
}

$UseCpu = Join-Path $Root "apps\kokoro-fastapi\.use-cpu"
$gpu = $false
if (Test-Path "\\.\nvidia0" -ErrorAction SilentlyContinue) { $gpu = $true }
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    & nvidia-smi -L 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $gpu = $true }
}
if (-not $gpu) {
    try {
        $info = docker info 2>$null | Out-String
        if ($info -match "nvidia") { $gpu = $true }
    } catch {}
}
if ($gpu) {
    if (Test-Path $UseCpu) { Remove-Item $UseCpu }
    Write-Host "Kokoro: GPU-image (v0.9.0-cu128)."
} else {
    New-Item -ItemType File -Force -Path $UseCpu | Out-Null
    Write-Host "Kokoro: CPU-image (v0.9.0)."
}

$Stt = Join-Path $Root "apps\stt-hotkey"
$Py = Join-Path $Stt ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    python -m venv (Join-Path $Stt ".venv")
    & $Py -m pip install -U pip
    & $Py -m pip install -r (Join-Path $Stt "requirements.txt")
}

$UserBin = Join-Path $env:USERPROFILE ".local\bin"
New-Item -ItemType Directory -Force -Path $UserBin | Out-Null

function ConvertTo-GitBashPath([string]$WinPath) {
    $p = $WinPath -replace '\\', '/'
    if ($p -match '^([A-Za-z]):(.*)$') {
        return '/' + $Matches[1].ToLower() + $Matches[2]
    }
    return $p
}
$unixRoot = ConvertTo-GitBashPath $Root
foreach ($name in @('tts', 'ttsoff', 'tts-en', 'tts-sv', 'tts-sel')) {
    $body = "#!/usr/bin/env bash`nexport TTSPRO_ROOT='$unixRoot'`nexec `"`$TTSPRO_ROOT/bin/$name`" `"`$@`"`n"
    [System.IO.File]::WriteAllText((Join-Path $UserBin $name), $body)
}
Copy-Item (Join-Path $Stt "windows\tts.ps1") (Join-Path $UserBin "tts.ps1") -Force
Copy-Item (Join-Path $Stt "windows\ttsoff.ps1") (Join-Path $UserBin "ttsoff.ps1") -Force

$Path = [Environment]::GetEnvironmentVariable("Path", "User")
if ($null -eq $Path) { $Path = "" }
if ($Path -notlike "*$UserBin*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserBin;$Path", "User")
    Write-Host "Lade $UserBin på användar-PATH."
}

$GitBashRc = Join-Path $env:USERPROFILE ".bashrc"
$line = 'export PATH="$HOME/.local/bin:$PATH"'
if (Test-Path $GitBashRc) {
    $txt = Get-Content $GitBashRc -Raw
    if ($txt -notmatch '\.local/bin') {
        Add-Content $GitBashRc "`n# local-voicestack-sv-eng`n$line`n"
        Write-Host "Lade PATH i Git Bash ~/.bashrc"
    }
} else {
    Set-Content $GitBashRc "# local-voicestack-sv-eng`n$line`n"
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$Wsh = New-Object -ComObject WScript.Shell
$start = $Wsh.CreateShortcut((Join-Path $Desktop "Starta röststack.lnk"))
$start.TargetPath = Join-Path $Root "tts.cmd"
$start.WorkingDirectory = $Root
$start.Save()
$stop = $Wsh.CreateShortcut((Join-Path $Desktop "Stoppa röststack.lnk"))
$stop.TargetPath = Join-Path $Root "ttsoff.cmd"
$stop.WorkingDirectory = $Root
$stop.Save()
Copy-Item (Join-Path $Root "tts.cmd") (Join-Path $UserBin "tts.cmd") -Force
Copy-Item (Join-Path $Root "ttsoff.cmd") (Join-Path $UserBin "ttsoff.cmd") -Force

Write-Host ""
Write-Host "Klart. Dubbelklicka tts.cmd eller skrivbordslänken Starta röststack."
Write-Host "  Git Bash:     tts"
Write-Host "  PowerShell:   tts.ps1"
Write-Host "Svensk TTS: egen nyckel i apps\azure-speech-gateway\.env — se README.md"
Write-Host "Brave unpacked: $Root\apps\kokoro-fastapi\brave-extension"
