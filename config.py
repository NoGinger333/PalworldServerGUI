import json
import os
import threading
import logging

logger = logging.getLogger(__name__)

class ManagerConfig:
    """
    アプリケーション設定管理モジュール（シングルトン）
    manager_config.json の読み込み・保存・更新を行う
    """
    _instance = None
    _lock = threading.Lock()
    
    # 実行ディレクトリ直下の manager_config.json
    CONFIG_PATH = "manager_config.json"
    
    DEFAULT_CONFIG = {
        "server_path": "/home/steam/palworld",
        "steamcmd_path": "/usr/games/steamcmd",
        "server_port": 8211,
        "rcon_enabled": True,
        "rcon_port": 25575,
        "rcon_password": "",
        "auto_restart_on_crash": True,
        "auto_update_on_restart": True,
        "restart_schedule_enabled": False,
        "restart_interval_hours": 6,
        "restart_warning_minutes": 5,
        "auto_backup": False,
        "backup_interval_hours": 1,
        "max_backups": 10,
        "backup_path": "/home/steam/palworld-backups",
        "launch_params": "-useperfthreads -NoAsyncLoadingThread -UseMultithreadForDS",
        "web_port": 5000,
        "web_password": "admin"
    }

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ManagerConfig, cls).__new__(cls)
                cls._instance._config = {}
                cls._instance.load()
        return cls._instance

    def load(self):
        """設定ファイルから読み込む。存在しない場合はデフォルト値で作成する。"""
        if os.path.exists(self.CONFIG_PATH):
            try:
                with open(self.CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # デフォルト値に既存の設定をマージ
                    self._config = self.DEFAULT_CONFIG.copy()
                    self._config.update(data)
                logger.info(f"設定ファイルを読み込みました: {self.CONFIG_PATH}")
            except Exception as e:
                logger.error(f"設定ファイルの読み込みに失敗しました: {e}")
                self._config = self.DEFAULT_CONFIG.copy()
        else:
            logger.info("設定ファイルが存在しないため、デフォルト値で新規作成します。")
            self._config = self.DEFAULT_CONFIG.copy()
            self.save()

    def save(self):
        """現在の設定をファイルに保存する。"""
        try:
            with open(self.CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info("設定ファイルを保存しました。")
        except Exception as e:
            logger.error(f"設定ファイルの保存に失敗しました: {e}")

    def get(self, key, default=None):
        """指定したキーの設定値を取得する。"""
        return self._config.get(key, default)

    def set(self, key, value):
        """指定したキーに設定値をセットし、保存する。"""
        self._config[key] = value
        self.save()

    def to_dict(self):
        """設定全体を辞書として返す。"""
        return self._config.copy()

    def update(self, update_dict):
        """複数の設定を一括更新し、保存する。"""
        self._config.update(update_dict)
        self.save()
