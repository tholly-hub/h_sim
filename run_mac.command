#!/usr/bin/env bash
# -------------------------------------------------------------
# macOS用 ダブルクリック実行ランチャー
# -------------------------------------------------------------

cd "$(dirname "$0")"

export PYTHONIOENCODING="utf-8"
export PYTHONPATH="."

# 画面をクリアして開始
clear

if command -v python3 &>/dev/null; then
    python3 main.py
elif command -v python &>/dev/null; then
    python main.py
else
    echo "============================================================"
    echo "[エラー] Python が見つかりませんでした。"
    echo "Python 3.10以上をインストールしてください。"
    echo "https://www.python.org/downloads/mac-osx/"
    echo "============================================================"
    read -p "Enterキーを押して終了してください..."
    exit 1
fi
