import os
import subprocess
import logging
import time

logger = logging.getLogger(__name__)

class SteamCMDManager:
    """
    SteamCMDのインストールとサーバー管理を行うクラス
    """
    def __init__(self, config):
        self.config = config
        self.app_id = "2394010" # パルワールド専用サーバーのAppID

    def get_steamcmd_executable(self) -> str:
        """実行可能なSteamCMDのパスを取得する。"""
        configured_path = self.config.get("steamcmd_path", "/usr/games/steamcmd")
        if os.path.exists(configured_path) and os.access(configured_path, os.X_OK):
            return configured_path
            
        import shutil
        which_path = shutil.which("steamcmd")
        if which_path:
            return which_path
            
        candidates = ["/usr/games/steamcmd", "/usr/bin/steamcmd", "/usr/local/bin/steamcmd"]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
                
        return configured_path

    def is_installed(self) -> bool:
        """SteamCMDがインストール済みか確認する。"""
        exe = self.get_steamcmd_executable()
        return os.path.exists(exe)

    def install(self, callback=None):
        """SteamCMDをインストールする(Ubuntu向け)。"""
        if self.is_installed():
            if callback:
                callback("SteamCMDは既にインストールされています。\n")
            return

        commands = [
            "sudo add-apt-repository multiverse -y",
            "sudo dpkg --add-architecture i386",
            "sudo apt update",
            "echo steam steam/question select I AGREE | sudo debconf-set-selections",
            "echo steam steam/license note '' | sudo debconf-set-selections",
            "sudo apt install -y steamcmd lib32gcc-s1"
        ]

        for cmd in commands:
            self._run_command(cmd, callback, shell=True)

        if self.is_installed():
            if callback:
                callback("SteamCMDのインストールが完了しました。\n")
        else:
            if callback:
                callback("SteamCMDのインストールに失敗した可能性があります。\n")

    def is_server_installed(self) -> bool:
        """パルワールドサーバーがインストール済みか確認する。"""
        server_path = os.path.expanduser(self.config.get("server_path"))
        executable = os.path.join(server_path, "PalServer.sh")
        return os.path.exists(executable)

    def install_server(self, callback=None):
        """パルワールドサーバーをインストールする。"""
        self._update_server_internal(callback, is_install=True)

    def update_server(self, callback=None):
        """パルワールドサーバーをアップデートする。"""
        self._update_server_internal(callback, is_install=False)

    def _update_server_internal(self, callback=None, is_install=False):
        steamcmd_path = self.get_steamcmd_executable()
        server_path = os.path.expanduser(self.config.get("server_path"))
        
        if not self.is_installed():
            if callback:
                callback("エラー: SteamCMDが見つかりません。先にSteamCMDをインストールしてください。\n")
            return

        try:
            os.makedirs(server_path, exist_ok=True)
        except Exception as e:
            if callback:
                callback(f"エラー: ディレクトリ '{server_path}' の作成に失敗しました (権限エラーなど): {e}\n")
            logger.error(f"ディレクトリ作成エラー: {e}")
            return
        
        action = "インストール" if is_install else "アップデート"
        if callback:
            callback(f"サーバーの{action}を開始します...\nディレクトリ: {server_path}\n")

        cmd = [
            steamcmd_path,
            "+force_install_dir", server_path,
            "+login", "anonymous",
            "+app_update", self.app_id, "validate",
            "+quit"
        ]

        self._run_command(cmd, callback, shell=False)
        
        if callback:
            callback(f"サーバーの{action}が完了しました。\n")

    def _run_command(self, cmd, callback=None, shell=False):
        """コマンドを実行し、出力をコールバックに渡す。"""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=shell
            )

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line and callback:
                    callback(line)
                    
            process.wait()
            
        except Exception as e:
            logger.error(f"コマンド実行エラー: {e}")
            if callback:
                callback(f"エラーが発生しました: {str(e)}\n")
