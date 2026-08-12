@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" "%~dp0test_db_connection.py"
echo.
echo Exit code: %ERRORLEVEL%
pause
