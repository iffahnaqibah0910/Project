@echo off
setlocal
cd /d "%~dp0"

echo Stopping anything already bound to port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr LISTENING') do (
  echo   killing PID %%p
  taskkill /F /PID %%p >nul 2>&1
)

echo Starting API on http://127.0.0.1:8000 ...
".\.venv\Scripts\uvicorn.exe" main:app --reload --host 127.0.0.1 --port 8000
