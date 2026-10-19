@echo off
rem Coleta e publica no site pelo computador local (usa o login do wrangler desta máquina).
rem Alternativa ao GitHub Actions, que faz o mesmo na nuvem todo dia.
cd /d "%~dp0"
if not exist dados mkdir dados
set PYTHONIOENCODING=utf-8
echo ===== %date% %time% >> dados\coleta.log
".venv\Scripts\python.exe" -m caca_vagas coletar --saida dados\vagas.sql >> dados\coleta.log 2>&1 || exit /b 1
cd web
call npx wrangler d1 execute caca-vagas --remote --file ..\dados\vagas.sql -y >> ..\dados\coleta.log 2>&1
