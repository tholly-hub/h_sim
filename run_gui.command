#!/usr/bin/env bash
# -------------------------------------------------------------
# macOS用 GUIデータ可視化＆レース再生システム ダブルクリック起動
# -------------------------------------------------------------

cd "$(dirname "$0")"

export PYTHONIOENCODING="utf-8"
export PYTHONPATH="."

clear
echo "============================================================"
echo "  競馬シミュレーションエンジン - GUIデータ可視化システム"
echo "============================================================"
echo "起動中... しばらくお待ちください。"

if command -v python3 &>/dev/null; then
    python3 main.py --gui "$@"
elif command -v python &>/dev/null; then
    python main.py --gui "$@"
else
    echo "============================================================"
    echo "[エラー] Python が見つかりませんでした。"
    echo "Python 3.10以上をインストールしてください。"
    echo "https://www.python.org/downloads/mac-osx/"
    echo "============================================================"
    read -p "Enterキーを押して終了してください..."
    exit 1
fi
