@echo off
@setlocal
cd /d "%~dp0"

:: 文字コードをUTF-8に設定
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONPATH=.

echo ============================================================
echo   競馬シミュレーションエンジン - GUIデータ可視化システム
echo ============================================================
echo 起動中... しばらくお待ちください。

:: Pythonの検索と実行 (py ランチャー優先、次に python)
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py main.py --gui %*
    goto :done
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python main.py --gui %*
    goto :done
)

echo [エラー] Python が見つかりませんでした。
echo Python 3.10以上をインストールし、PATHに追加してください。
echo https://www.python.org/
pause

:done
endlocal
