@echo off
setlocal
echo ===================================================
echo   Starting Expense Tracker (local server)
echo ===================================================
echo Server: http://localhost:8010
echo API docs: http://localhost:8010/docs
echo Press Ctrl+C to stop the server.
echo ===================================================
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
cd /d "%~dp0package"
"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
pause
