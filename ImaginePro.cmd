@echo off
title ImaginePro
if "%~1"=="" if exist "%~dp0ImaginePro.exe" (
  start "" "%~dp0ImaginePro.exe"
  exit /b 0
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
