@echo off
rem Dois cliques no Windows: liga o motor de busca, o WhatsApp (WAHA) e o painel. Sem Docker.
cd /d "%~dp0"
title Prospecta
set "PY=%APPDATA%\uv\python\cpython-3.12-windows-x86_64-none\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -X utf8 scripts\iniciar.py %*
