@echo off
REM Dubbelklicka för att starta stacken (Windows).
set SCRIPT=%~dp0apps\stt-hotkey\windows\tts.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
if errorlevel 1 pause
