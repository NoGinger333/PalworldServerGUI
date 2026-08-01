# 🎮 PalServer Manager

Ubuntu上でパルワールド（Palworld）専用サーバーをWebブラウザから管理できるGUIツールです。

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-green?logo=flask)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ 主な機能

| 機能 | 説明 |
|:--|:--|
| 🔧 **SteamCMDワンクリックインストール** | SteamCMDとパルワールドサーバーをGUIからインストール |
| ▶️ **サーバー操作** | 起動・停止・再起動をブラウザから操作 |
| 🔄 **自動再起動** | クラッシュ検出時の自動再起動 + スケジュール再起動 |
| ⬆️ **自動アップデート** | 再起動時に自動でサーバーをアップデート |
| ⚙️ **設定エディタ** | PalWorldSettings.ini の全設定をGUIで編集 |
| 🖥️ **リアルタイムコンソール** | サーバーログの閲覧 + RCONコマンド実行 |
| 👥 **プレイヤー管理** | オンラインプレイヤーの確認・キック・BAN |
| 💾 **バックアップ管理** | ワールドデータの手動/自動バックアップと復元 |
| 📊 **リソース監視** | CPU・メモリ使用率のリアルタイム表示 |

## 📸 スクリーンショット

<!-- スクリーンショットをここに追加 -->
> ダークテーマ + グラスモーフィズムのモダンなWeb UIで操作できます。

## 🚀 インストール方法

### 必要環境
- **Ubuntu** 20.04 / 22.04 / 24.04（Debian系も対応）
- **Python 3.8** 以上
- **sudo権限**（SteamCMDインストール時に必要）

### 手順

```bash
# 1. リポジトリをクローン
git clone https://github.com/<your-username>/palserver-manager.git
cd palserver-manager

# 2. インストールスクリプトを実行
chmod +x install.sh run.sh
bash install.sh

# 3. サーバーを起動
./run.sh
```

ブラウザで `http://<サーバーIP>:5000` にアクセスしてください。

> **デフォルトパスワード: `admin`**
> ⚠️ 初回ログイン後、マネージャー設定からパスワードを変更してください。

## 📖 初回セットアップガイド

1. ブラウザでログイン（パスワード: `admin`）
2. ダッシュボードの **「Install SteamCMD」** をクリック
3. 完了後、**「Install Server」** をクリック
4. **「🔧 マネージャー設定」** でRCONパスワード等を設定
5. **「⚙️ サーバー設定」** でゲームバランス等を調整
6. **「▶️ Start」** ボタンでサーバー起動！

## ⚙️ 設定

### マネージャー設定（`manager_config.json`）

| 項目 | デフォルト値 | 説明 |
|:--|:--|:--|
| `server_path` | `/home/steam/palworld` | サーバーインストール先 |
| `server_port` | `8211` | ゲームサーバーポート (UDP) |
| `rcon_port` | `25575` | RCONポート |
| `web_port` | `5000` | 管理画面のポート |
| `web_password` | `admin` | 管理画面のパスワード |
| `auto_restart_on_crash` | `true` | クラッシュ時自動再起動 |
| `auto_update_on_restart` | `true` | 再起動時自動アップデート |

GUIの「🔧 マネージャー設定」画面からも変更できます。

### ファイアウォール設定

```bash
# ゲームサーバーポート
sudo ufw allow 8211/udp

# 管理画面ポート（必要に応じて）
sudo ufw allow 5000/tcp
```

## 🏗️ プロジェクト構成

```
palserver-manager/
├── app.py                 # Flask REST API + WebSocket
├── config.py              # 設定管理
├── server_manager.py      # サーバープロセス管理
├── steamcmd_manager.py    # SteamCMD管理
├── rcon_client.py         # RCON プロトコル実装
├── settings_parser.py     # PalWorldSettings.ini パーサー
├── backup_manager.py      # バックアップ管理
├── scheduler.py           # スケジュール管理
├── requirements.txt       # Python依存パッケージ
├── install.sh             # インストールスクリプト
├── run.sh                 # 起動スクリプト
├── templates/
│   └── index.html         # Web UI (SPA)
└── static/
    ├── css/style.css      # スタイルシート
    └── js/app.js          # フロントエンドJS
```

## 🔒 セキュリティに関する注意

- デフォルトパスワード (`admin`) は必ず変更してください
- 管理画面を外部に公開する場合は、nginxリバースプロキシ + HTTPS の使用を推奨します
- ファイアウォールで管理画面ポート (5000) へのアクセスを制限することを推奨します

### HTTPS化（推奨）

```bash
# nginx + Let's Encrypt を使用する場合
sudo apt install nginx certbot python3-certbot-nginx

# nginx設定例
server {
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 🔧 systemd サービス化（オプション）

バックグラウンドで自動起動させたい場合：

```bash
sudo nano /etc/systemd/system/palserver-manager.service
```

```ini
[Unit]
Description=PalServer Manager Web UI
After=network.target

[Service]
Type=simple
User=steam
WorkingDirectory=/opt/palserver-manager
ExecStart=/opt/palserver-manager/venv/bin/python3 /opt/palserver-manager/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable palserver-manager
sudo systemctl start palserver-manager
```

## 📝 ライセンス

MIT License

## 🤝 コントリビューション

Issue・Pull Request 歓迎です！
