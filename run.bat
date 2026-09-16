@echo off
@setlocal
cd /d "%~dp0"

:: 文字コードをUTF-8に設定
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONPATH=.

:: 引数がある場合はそのまま渡して実行
if not "%~1"=="" (
    goto :run_with_args
)

:: 引数がない場合は選択メニューを表示
:menu
cls
echo ============================================================
echo   競馬シミュレーションエンジン (Horse Racing Sim)
echo ============================================================
echo  [1] GUI 画面（可視化＆レース再生）を起動
echo  [2] CUI 対話型メニューを起動
echo  [3] 終了
echo ============================================================
set /p CHOICE="番号を入力してください (1-3): "

if "%CHOICE%"=="1" (
    goto :run_gui
)
if "%CHOICE%"=="2" (
    goto :run_menu
)
if "%CHOICE%"=="3" (
    goto :done
)
goto :menu

:run_gui
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py main.py --gui
    goto :done
)
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python main.py --gui
    goto :done
)
goto :py_not_found

:run_menu
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py main.py --menu
    goto :done
)
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python main.py --menu
    goto :done
)
goto :py_not_found

:run_with_args
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
goto :py_not_found

:py_not_found
echo [エラー] Python が見つかりませんでした。
echo Python 3.10以上をインストールし、PATHに追加してください。
echo https://www.python.org/
pause

:done
endlocal
