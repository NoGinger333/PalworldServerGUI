import threading
import time
import logging

logger = logging.getLogger(__name__)

class SchedulerManager:
    """
    スケジュール管理（定期再起動・自動バックアップ）を行うクラス
    """
    def __init__(self, config, server_manager, backup_manager):
        self.config = config
        self.server_manager = server_manager
        self.backup_manager = backup_manager
        
        self._thread = None
        self._stop_event = threading.Event()
        
        self.last_restart_time = time.time()
        self.last_backup_time = time.time()
        self.warning_sent = False

    def start(self):
        """スケジューラースレッドを開始する。"""
        if self._thread and self._thread.is_alive():
            return
            
        self._stop_event.clear()
        self.last_restart_time = time.time()
        self.last_backup_time = time.time()
        
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("スケジューラーを開始しました。")

    def stop(self):
        """スケジューラースレッドを停止する。"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("スケジューラーを停止しました。")

    def update_config(self):
        """設定変更時にスケジュール情報をリセットする。"""
        self.last_restart_time = time.time()
        self.last_backup_time = time.time()
        self.warning_sent = False

    def _run(self):
        """定期的にチェックを行うループ。"""
        while not self._stop_event.is_set():
            now = time.time()
            
            # 定期再起動チェック
            if self.config.get("restart_schedule_enabled"):
                interval_hours = self.config.get("restart_interval_hours", 6)
                warning_minutes = self.config.get("restart_warning_minutes", 5)
                
                interval_seconds = interval_hours * 3600
                next_restart = self.last_restart_time + interval_seconds
                
                # 警告時刻チェック
                warning_seconds = warning_minutes * 60
                if not self.warning_sent and (next_restart - now) <= warning_seconds and (next_restart - now) > 0:
                    if self.server_manager.status == 'running' and self.config.get("rcon_enabled"):
                        try:
                            self.server_manager.broadcast(f"Server_will_restart_in_{warning_minutes}_minutes")
                            self.warning_sent = True
                            logger.info("再起動予告をブロードキャストしました。")
                        except Exception as e:
                            logger.error(f"再起動予告エラー: {e}")
                            
                # 再起動実行
                if now >= next_restart:
                    logger.info("スケジュールされた再起動を実行します。")
                    if self.server_manager.status == 'running':
                        # 再起動時はアップデート設定も考慮
                        update = self.config.get("auto_update_on_restart", False)
                        self.server_manager.restart(update=update)
                    
                    self.last_restart_time = now
                    self.warning_sent = False
                    
            # 自動バックアップチェック
            if self.config.get("auto_backup"):
                interval_hours = self.config.get("backup_interval_hours", 1)
                interval_seconds = interval_hours * 3600
                next_backup = self.last_backup_time + interval_seconds
                
                if now >= next_backup:
                    logger.info("スケジュールされたバックアップを実行します。")
                    self.backup_manager.create_backup()
                    self.last_backup_time = now
            
            # 10秒に1回チェック
            time.sleep(10)

    def get_schedule_info(self) -> dict:
        """次回実行予定などの情報を返す。"""
        now = time.time()
        info = {
            "restart": {
                "enabled": self.config.get("restart_schedule_enabled"),
                "next_time": None
            },
            "backup": {
                "enabled": self.config.get("auto_backup"),
                "next_time": None
            }
        }
        
        if info["restart"]["enabled"]:
            interval = self.config.get("restart_interval_hours", 6) * 3600
            info["restart"]["next_time"] = self.last_restart_time + interval
            
        if info["backup"]["enabled"]:
            interval = self.config.get("backup_interval_hours", 1) * 3600
            info["backup"]["next_time"] = self.last_backup_time + interval
            
        return info
