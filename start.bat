@echo off
cd /d "%~dp0"
rem Starts the app without a console window (errors are written to spot2rb\data\app.log).
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m spot2rb.app
) else (
    start "" pythonw -m spot2rb.app
)
