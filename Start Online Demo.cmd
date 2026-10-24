@echo off
cd /d "%~dp0"
start "" /b "%~dp0.venv\Scripts\pythonw.exe" "%~dp0cloud\start_demo.pyw"
