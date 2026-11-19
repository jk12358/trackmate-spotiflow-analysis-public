@echo off
rem Double-click this file to start the diffusion analysis app on this PC.
rem The steps and the Japanese messages are in start_app.ps1 (cmd cannot show UTF-8 text reliably).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_app.ps1"
if errorlevel 1 pause
