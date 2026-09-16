@echo off
@setlocal
cd /d "%~dp0"

:: 文字コードをUTF-8に設定
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONPATH=.

echo ============================================================
echo   競馬シミュレーションエンジン - 対話型メニュー
echo ============================================================

:: Pythonの検索と実行 (py ランチャー優先、次に python)
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py main.py --menu %*
    goto :done
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python main.py --menu %*
    goto :done
)

echo [エラー] Python が見つかりませんでした。
echo Python 3.10以上をインストールし、PATHに追加してください。
echo https://www.python.org/
pause

:done
endlocal
