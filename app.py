import os
from flask import Flask, request, jsonify, session, render_template
from flask_socketio import SocketIO, emit
from functools import wraps
import logging
import threading

from config import ManagerConfig
from steamcmd_manager import SteamCMDManager
from backup_manager import BackupManager
from server_manager import ServerManager
from scheduler import SchedulerManager
from settings_parser import PalWorldSettings

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.urandom(24) # セッション用シークレットキー

# SocketIO 初期化 (CORS設定等)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# マネージャー類の初期化
config = ManagerConfig()
steamcmd_mgr = SteamCMDManager(config)
backup_mgr = BackupManager(config)
server_mgr = ServerManager(config, steamcmd_mgr, backup_mgr)
scheduler_mgr = SchedulerManager(config, server_mgr, backup_mgr)

# サーバーログをWebSocketに転送するコールバックを登録
def on_server_log(message):
    socketio.emit('log', {'data': message}, namespace='/console')
server_mgr.add_log_callback(on_server_log)

# 認証デコレータ
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# Routes
# ==========================================

@app.route('/')
def index():
    """templates/index.html を返す"""
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    password = data.get('password', '')
    
    if password == config.get('web_password'):
        session['logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Invalid password'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return jsonify({'success': True})

# --- Server Management ---

@app.route('/api/status', methods=['GET'])
@login_required
def get_status():
    status = server_mgr.get_status()
    # SteamCMD/サーバーインストール状態も含める
    status['steamcmd_installed'] = steamcmd_mgr.is_installed()
    status['server_installed'] = steamcmd_mgr.is_server_installed()
    status['max_players'] = 32
    # ステータス変更時にフロントエンドに通知するための措置
    socketio.emit('status_update', status, namespace='/console')
    return jsonify(status)

@app.route('/api/server/start', methods=['POST'])
@login_required
def start_server():
    server_mgr.start()
    return jsonify({'success': True})

@app.route('/api/server/stop', methods=['POST'])
@login_required
def stop_server():
    server_mgr.stop()
    return jsonify({'success': True})

@app.route('/api/server/restart', methods=['POST'])
@login_required
def restart_server():
    data = request.json or {}
    update = data.get('update', False)
    server_mgr.restart(update=update)
    return jsonify({'success': True})

@app.route('/api/server/update', methods=['POST'])
@login_required
def update_server():
    if server_mgr.status in ['running', 'starting']:
        return jsonify({'success': False, 'message': 'サーバー停止中のみアップデート可能です。'}), 400
    server_mgr.status = 'updating'
    def _update():
        steamcmd_mgr.update_server(callback=server_mgr._emit_log)
        server_mgr.status = 'stopped'
    threading.Thread(target=_update, daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/server/save', methods=['POST'])
@login_required
def save_world():
    """ワールドデータをセーブする。"""
    try:
        res = server_mgr.execute_rcon('Save')
        return jsonify({'success': True, 'response': res})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- SteamCMD ---

@app.route('/api/steamcmd/status', methods=['GET'])
@login_required
def get_steamcmd_status():
    return jsonify({
        'installed': steamcmd_mgr.is_installed(),
        'server_installed': steamcmd_mgr.is_server_installed()
    })

@app.route('/api/steamcmd/install', methods=['POST'])
@login_required
def install_steamcmd():
    threading.Thread(target=steamcmd_mgr.install, args=(server_mgr._emit_log,), daemon=True).start()
    return jsonify({'success': True, 'message': 'インストールを開始しました'})

@app.route('/api/steamcmd/install-server', methods=['POST'])
@login_required
def install_server():
    threading.Thread(target=steamcmd_mgr.install_server, args=(server_mgr._emit_log,), daemon=True).start()
    return jsonify({'success': True, 'message': 'サーバーインストールを開始しました'})

# --- Settings (PalWorldSettings.ini) ---

@app.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    ini_path = os.path.join(config.get('server_path'), "Pal", "Saved", "Config", "LinuxServer", "PalWorldSettings.ini")
    parser = PalWorldSettings(ini_path)
    settings = parser.load()
    metadata = parser.get_settings_metadata()
    return jsonify({'settings': settings, 'metadata': metadata})

@app.route('/api/settings', methods=['POST'])
@login_required
def save_settings():
    data = request.json
    ini_path = os.path.join(config.get('server_path'), "Pal", "Saved", "Config", "LinuxServer", "PalWorldSettings.ini")
    parser = PalWorldSettings(ini_path)
    try:
        parser.save(data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- RCON / Players ---

@app.route('/api/players', methods=['GET'])
@login_required
def get_players():
    if not config.get('rcon_enabled'):
        return jsonify([])
    return jsonify(server_mgr.get_players())

@app.route('/api/players/kick', methods=['POST'])
@login_required
def kick_player():
    data = request.json
    steam_id = data.get('steam_id')
    try:
        res = server_mgr.kick_player(steam_id)
        return jsonify({'success': True, 'response': res})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/players/ban', methods=['POST'])
@login_required
def ban_player():
    data = request.json
    steam_id = data.get('steam_id')
    try:
        res = server_mgr.ban_player(steam_id)
        return jsonify({'success': True, 'response': res})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/broadcast', methods=['POST'])
@login_required
def broadcast():
    data = request.json
    message = data.get('message', '')
    try:
        res = server_mgr.broadcast(message)
        return jsonify({'success': True, 'response': res})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/rcon', methods=['POST'])
@login_required
def execute_rcon():
    data = request.json
    command = data.get('command', '')
    try:
        res = server_mgr.execute_rcon(command)
        return jsonify({'success': True, 'response': res})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Backups ---

@app.route('/api/backups', methods=['GET'])
@login_required
def list_backups():
    return jsonify(backup_mgr.list_backups())

@app.route('/api/backups/create', methods=['POST'])
@login_required
def create_backup():
    result = backup_mgr.create_backup()
    if result:
        return jsonify({'success': True, 'backup': result})
    return jsonify({'success': False, 'message': 'バックアップの作成に失敗しました'}), 500

@app.route('/api/backups/restore', methods=['POST'])
@login_required
def restore_backup():
    if server_mgr.status in ['running', 'starting']:
        return jsonify({'success': False, 'message': '復元を行う前にサーバーを停止してください。'}), 400
        
    data = request.json
    filename = data.get('filename')
    success = backup_mgr.restore_backup(filename)
    return jsonify({'success': success})

@app.route('/api/backups/<filename>', methods=['DELETE'])
@login_required
def delete_backup(filename):
    success = backup_mgr.delete_backup(filename)
    return jsonify({'success': success})

# --- Manager Config ---

@app.route('/api/manager-config', methods=['GET'])
@login_required
def get_manager_config():
    return jsonify(config.to_dict())

@app.route('/api/manager-config', methods=['POST'])
@login_required
def save_manager_config():
    data = request.json
    config.update(data)
    scheduler_mgr.update_config()
    return jsonify({'success': True})

# --- Others ---

@app.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    return jsonify(server_mgr.get_recent_logs())

@app.route('/api/schedule', methods=['GET'])
@login_required
def get_schedule():
    return jsonify(scheduler_mgr.get_schedule_info())

# ==========================================
# Startup
# ==========================================

if __name__ == '__main__':
    # スケジューラー起動
    scheduler_mgr.start()
    
    # サーバー開始
    port = config.get('web_port', 5000)
    logger.info(f"PalServer Manager Web UI を起動します。ポート: {port}")
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
