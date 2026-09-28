@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=.venv\Scripts\python.exe"
if not defined PYTHON_CMD (
    where py >nul 2>nul && set "PYTHON_CMD=py"
)
if not defined PYTHON_CMD (
    where python >nul 2>nul && set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo [ERROR] Python not found.
    echo Please install Python 3.10 or higher and add it to PATH.
    pause
    exit /b 1
)

set PYTHONPATH=.
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo Starting GUI...
%PYTHON_CMD% main.py --gui %*
if errorlevel 1 (
    echo.
    echo [Application finished with error level: %ERRORLEVEL%]
    pause
)
