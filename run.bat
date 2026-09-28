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

if not "%~1"=="" (
    %PYTHON_CMD% main.py %*
    goto :eof
)

:menu
cls
echo ============================================================
echo   Horse Racing Simulation Engine (競馬シミュレーション)
echo ============================================================
echo  [1] GUI (可視化＆レース再生)
echo  [2] CUI 対話型メニュー
echo  [3] 終了
echo ============================================================
set /p CHOICE="番号を入力 (1-3): "

if "%CHOICE%"=="1" (
    %PYTHON_CMD% main.py --gui
    goto :eof
)
if "%CHOICE%"=="2" (
    %PYTHON_CMD% main.py --menu
    goto :eof
)
if "%CHOICE%"=="3" (
    goto :eof
)
goto :menu
