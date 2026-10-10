@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_navigation_assistant.ps1"
if errorlevel 1 pause
