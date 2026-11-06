@echo off
rem Central unificada. Por padrao, abre sem retomar envios automaticos.
cd /d "%~dp0"
title Prospecta SITH.IA
if /I "%~1"=="--automacoes" goto automacoes
call "%~dp0Prospeccao.cmd" --sem-automacoes %*
goto :eof
:automacoes
rem O operador escolheu retomar as rotinas ja configuradas no CRM.
call "%~dp0Prospeccao.cmd" %*
