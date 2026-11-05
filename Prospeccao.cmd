@echo off
rem Liga motores e painel; WhatsApp (WAHA) usa Docker Desktop.
cd /d "%~dp0"
title Central SITH.IA
set "PY=%APPDATA%\uv\python\cpython-3.12-windows-x86_64-none\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -X utf8 scripts\iniciar.py %*
