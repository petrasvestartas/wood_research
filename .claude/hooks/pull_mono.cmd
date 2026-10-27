@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0pull_mono.ps1" %*
exit /b %errorlevel%
