@echo off
rem Coleta diária, chamada pelo Agendador de Tarefas do Windows.
cd /d "%~dp0"
if not exist dados mkdir dados
set PYTHONIOENCODING=utf-8
echo ===== %date% %time% >> dados\coleta.log
".venv\Scripts\python.exe" -m caca_vagas coletar >> dados\coleta.log 2>&1
