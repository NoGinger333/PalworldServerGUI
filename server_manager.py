import os
import subprocess
import threading
import time
import collections
import logging
import re
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from rcon_client import RconClient, RconError

logger = logging.getLogger(__name__)

class ServerManager:
    """
    サーバープロセスの管理を行うクラス
    """
    def __init__(self, config, steamcmd, backup):
        self.config = config
        self.steamcmd = steamcmd
        self.backup = backup
        
        self.process = None
        self.status = 'stopped'  # stopped, starting, running, stopping, updating
        self.log_buffer = collections.deque(maxlen=1000)
        self._monitor_thread = None
        self._log_callbacks = []
        self._stop_event = threading.Event()
        self.start_time = None

    def add_log_callback(self, callback):
        """ログ受信時のコールバックを登録する。"""
        self._log_callbacks.append(callback)

    def _emit_log(self, message):
        """ログをバッファに追加し、コールバックを呼び出す。"""
        if not message.endswith('\n'):
            message += '\n'
        self.log_buffer.append(message)
        for cb in self._log_callbacks:
            try:
                cb(message)
            except Exception as e:
                logger.error(f"ログコールバックエラー: {e}")

    def get_recent_logs(self, n=100) -> list:
        """最新のログを取得する。"""
        return list(self.log_buffer)[-n:]

    def start(self):
        """サーバーを起動する。"""
        if self.status in ['running', 'starting', 'updating']:
            return

        if not self.steamcmd.is_server_installed():
            self._emit_log("エラー: サーバーがインストールされていません。")
            return

        self.status = 'starting'
        self._stop_event.clear()
        
        server_path = self.config.get("server_path")
        executable = os.path.join(server_path, "PalServer.sh")
        launch_params = self.config.get("launch_params", "").split()
        
        cmd = [executable] + launch_params
        
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=server_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            self.start_time = time.time()
            self.status = 'running'
            self._emit_log("サーバープロセスを起動しました。")
            
            # 出力読み取りとプロセス監視のためのスレッドを開始
            self._monitor_thread = threading.Thread(target=self._monitor_process, daemon=True)
            self._monitor_thread.start()
            
        except Exception as e:
            self.status = 'stopped'
            self._emit_log(f"サーバー起動エラー: {e}")
            logger.error(f"サーバー起動エラー: {e}")

    def _monitor_process(self):
        """プロセスの標準出力を読み取り、プロセス終了を監視する。"""
        if not self.process:
            return

        # 標準出力を読み取る
        for line in iter(self.process.stdout.readline, ''):
            if not line and self.process.poll() is not None:
                break
            if line:
                self._emit_log(line)
        
        self.process.wait()
        
        # プロセスが終了した
        exit_code = self.process.returncode
        self._emit_log(f"サーバープロセスが終了しました (終了コード: {exit_code})")
        
        was_running = self.status == 'running'
        self.process = None
        self.start_time = None
        
        if self.status != 'updating':
            self.status = 'stopped'
        
        # 予期せぬ終了の場合は自動再起動
        if was_running and not self._stop_event.is_set():
            if self.config.get("auto_restart_on_crash"):
                self._emit_log("クラッシュを検知しました。自動再起動を行います...")
                
                if self.config.get("auto_update_on_restart"):
                    self.status = 'updating'
                    self.steamcmd.update_server(callback=self._emit_log)
                
                time.sleep(5)  # 少し待ってから再起動
                self.start()

    def stop(self, save_first=True):
        """サーバーを停止する。"""
        if self.status not in ['running', 'starting']:
            return

        self.status = 'stopping'
        self._stop_event.set()
        
        try:
            if save_first and self.config.get("rcon_enabled"):
                self._emit_log("セーブとシャットダウンコマンドを送信します...")
                self.execute_rcon("Save")
                time.sleep(2)
                self.execute_rcon("Shutdown 10 Server_is_shutting_down")
                
                # 15秒間プロセスの終了を待つ
                for _ in range(15):
                    if self.process is None or self.process.poll() is not None:
                        break
                    time.sleep(1)
            
            if self.process and self.process.poll() is None:
                self._emit_log("プロセスを強制終了します。")
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    
        except Exception as e:
            self._emit_log(f"サーバー停止中のエラー: {e}")
            if self.process:
                self.process.kill()
                
        self.process = None
        self.status = 'stopped'

    def restart(self, update=False):
        """サーバーを再起動する。"""
        threading.Thread(target=self._restart_task, args=(update,), daemon=True).start()

    def _restart_task(self, update):
        self.stop(save_first=True)
        # 停止を待機
        while self.status != 'stopped':
            time.sleep(1)
            
        if update:
            self.status = 'updating'
            self.steamcmd.update_server(callback=self._emit_log)
            self.status = 'stopped'
            
        self.start()

    def get_status(self) -> dict:
        """サーバーのステータスを取得する。"""
        uptime = 0
        if self.start_time and self.status == 'running':
            uptime = int(time.time() - self.start_time)
            
        cpu_percent = 0.0
        memory_mb = 0.0
        
        if self.process and HAS_PSUTIL:
            try:
                p = psutil.Process(self.process.pid)
                cpu_percent = p.cpu_percent(interval=0.1)
                memory_info = p.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        player_count = 0
        if self.status == 'running' and self.config.get("rcon_enabled"):
            try:
                players = self.get_players()
                player_count = len(players)
            except Exception:
                pass
            
        return {
            "status": self.status,
            "uptime": uptime,
            "cpu_percent": round(cpu_percent, 1),
            "memory_mb": round(memory_mb, 1),
            "player_count": player_count,
            "version": "Unknown" # RCONから取得できる場合は設定
        }

    def execute_rcon(self, command: str) -> str:
        """RCONコマンドを実行する。"""
        if not self.config.get("rcon_enabled"):
            raise Exception("RCONが無効になっています。")
            
        host = "127.0.0.1"
        port = self.config.get("rcon_port")
        password = self.config.get("rcon_password")
        
        with RconClient(host, port, password) as rcon:
            return rcon.send_command(command)

    def get_players(self) -> list:
        """接続中のプレイヤー一覧を取得する。"""
        try:
            resp = self.execute_rcon("ShowPlayers")
            # レスポンス例:
            # name,playeruid,steamid
            # Player1,123456,76561198...
            lines = resp.strip().split('\n')
            if len(lines) <= 1:
                return []
                
            players = []
            for line in lines[1:]: # ヘッダをスキップ
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    players.append({
                        "name": parts[0],
                        "playeruid": parts[1],
                        "steamid": parts[2]
                    })
            return players
        except Exception as e:
            logger.error(f"プレイヤー一覧取得エラー: {e}")
            return []

    def kick_player(self, steam_id: str) -> str:
        """プレイヤーをキックする。"""
        return self.execute_rcon(f"KickPlayer {steam_id}")

    def ban_player(self, steam_id: str) -> str:
        """プレイヤーをBANする。"""
        return self.execute_rcon(f"BanPlayer {steam_id}")

    def broadcast(self, message: str) -> str:
        """サーバー内にメッセージをブロードキャストする。空白はアンダースコアに変換。"""
        safe_msg = message.replace(" ", "_")
        return self.execute_rcon(f"Broadcast {safe_msg}")
