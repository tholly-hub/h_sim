@echo off
@setlocal
cd /d "%~dp0"

:: Set UTF-8 encoding
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

:: Try py launcher first, fallback to python
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py main.py %*
    goto :done
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python main.py %*
    goto :done
)

echo [ERROR] Python not found. Please install Python 3.10+ and add it to PATH.
pause

:done
endlocal
