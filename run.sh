#!/usr/bin/env bash
# -------------------------------------------------------------
# 競馬シミュレーションエンジン 実行用シェルスクリプト (macOS / Linux)
# -------------------------------------------------------------

cd "$(dirname "$0")"

export PYTHONIOENCODING="utf-8"

if command -v python3 &>/dev/null; then
    python3 main.py "$@"
elif command -v python &>/dev/null; then
    python main.py "$@"
else
    echo "[エラー] Python が見つかりませんでした。Python 3.10+ をインストールしてください。"
    exit 1
fi
