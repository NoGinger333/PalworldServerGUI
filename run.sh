#!/bin/bash
# =============================================================================
# PalServer Manager 起動スクリプト
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"

# 仮想環境確認
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ 仮想環境が見つかりません。先にインストールスクリプトを実行してください:"
    echo "   bash install.sh"
    exit 1
fi

# 仮想環境アクティベート
source "${VENV_DIR}/bin/activate"

echo "============================================="
echo "  🎮 PalServer Manager を起動しています..."
echo "============================================="
echo ""

# アプリケーション起動
cd "$SCRIPT_DIR"
python3 app.py

# 終了時
deactivate
