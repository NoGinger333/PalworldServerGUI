#!/bin/bash
# =============================================================================
# PalServer Manager インストールスクリプト
# Ubuntu上でパルワールド専用サーバー管理GUIツールをセットアップします
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"

echo "============================================="
echo "  🎮 PalServer Manager インストーラー"
echo "============================================="
echo ""

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 関数: 成功メッセージ
success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# 関数: 警告メッセージ
warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# 関数: エラーメッセージ
error() {
    echo -e "${RED}✗ $1${NC}"
}

# 1. OS確認
echo "📋 システム確認中..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [[ "$ID" != "ubuntu" && "$ID_LIKE" != *"ubuntu"* && "$ID_LIKE" != *"debian"* ]]; then
        warn "このスクリプトはUbuntu/Debian系OS向けです。他のOSでは動作しない可能性があります。"
    else
        success "OS: $PRETTY_NAME"
    fi
else
    warn "OS情報を取得できません。Ubuntu/Debian系OSを想定しています。"
fi
echo ""

# 2. システムパッケージとSteamCMDの自動インストール
echo "📦 システムパッケージ (Python3, pip, venv, SteamCMD) を確認・インストール中..."
sudo add-apt-repository multiverse -y > /dev/null 2>&1 || true
sudo dpkg --add-architecture i386 > /dev/null 2>&1 || true
sudo apt update -y > /dev/null 2>&1 || true

# SteamCMD ライセンス自動同意
echo steam steam/question select I AGREE | sudo debconf-set-selections > /dev/null 2>&1 || true
echo steam steam/license note '' | sudo debconf-set-selections > /dev/null 2>&1 || true

# 一括インストール
sudo apt install -y python3 python3-pip python3-venv python3-full steamcmd lib32gcc-s1 > /dev/null 2>&1 || true
success "Python3 / pip / venv / SteamCMD のセットアップが完了しました"
echo ""

# 3. 仮想環境作成
echo "🏗️  仮想環境を作成中..."
if [ -d "$VENV_DIR" ] && [ ! -f "${VENV_DIR}/bin/activate" ]; then
    warn "壊れた仮想環境を検出しました。再作成します..."
    rm -rf "$VENV_DIR"
fi

if [ -d "$VENV_DIR" ]; then
    warn "仮想環境は既に存在します: ${VENV_DIR}"
else
    python3 -m venv "$VENV_DIR"
    success "仮想環境を作成しました: ${VENV_DIR}"
fi

# 6. 依存パッケージインストール
echo "📥 依存パッケージをインストール中..."
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip -q
pip install -r "${SCRIPT_DIR}/requirements.txt" -q
success "依存パッケージをインストールしました"
deactivate
echo ""

# 7. 初期設定ファイル生成
if [ ! -f "${SCRIPT_DIR}/manager_config.json" ]; then
    echo "⚙️  初期設定ファイルを生成中..."
    cat > "${SCRIPT_DIR}/manager_config.json" << EOF
{
    "server_path": "${HOME}/palworld",
    "steamcmd_path": "/usr/games/steamcmd",
    "server_port": 8211,
    "rcon_enabled": true,
    "rcon_port": 25575,
    "rcon_password": "",
    "auto_restart_on_crash": true,
    "auto_update_on_restart": true,
    "restart_schedule_enabled": false,
    "restart_interval_hours": 6,
    "restart_warning_minutes": 5,
    "auto_backup": false,
    "backup_interval_hours": 1,
    "max_backups": 10,
    "backup_path": "${HOME}/palworld-backups",
    "launch_params": "-useperfthreads -NoAsyncLoadingThread -UseMultithreadForDS",
    "web_port": 5000,
    "web_password": "admin"
}
EOF
    success "初期設定ファイルを生成しました"
else
    warn "設定ファイルは既に存在します。スキップします。"
fi

# 8. パルワールド専用サーバーの自動ダウンロード・インストール
SERVER_PATH="${HOME}/palworld"
if [ ! -f "${SERVER_PATH}/PalServer.sh" ]; then
    echo "🎮 パルワールド専用サーバーをダウンロード・インストール中 (数分かかります)..."
    mkdir -p "${SERVER_PATH}"
    STEAMCMD_EXE="/usr/games/steamcmd"
    if [ ! -f "$STEAMCMD_EXE" ]; then
        STEAMCMD_EXE=$(which steamcmd 2>/dev/null || echo "steamcmd")
    fi
    "$STEAMCMD_EXE" +force_install_dir "${SERVER_PATH}" +login anonymous +app_update 2394010 validate +quit || true
    success "パルワールド専用サーバーのダウンロードが完了しました"
else
    success "パルワールド専用サーバーは既にインストールされています"
fi

# 9. 実行権限付与
chmod +x "${SCRIPT_DIR}/run.sh"
echo ""

echo "============================================="
echo -e "${GREEN}  ✅ オールインワン インストール完了！${NC}"
echo "============================================="
echo ""
echo "  次のステップ:"
echo "  1. サーバーを起動:   ./run.sh"
echo "  2. ブラウザでアクセス: http://localhost:5000"
echo "  3. 「▶️ Start」ボタンを押して即遊べます！"
echo ""
