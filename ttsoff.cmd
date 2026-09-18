@echo off
set SCRIPT=%~dp0apps\stt-hotkey\windows\ttsoff.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
if errorlevel 1 pause
