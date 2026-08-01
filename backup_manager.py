import os
import tarfile
import datetime
import glob
import logging
import shutil

logger = logging.getLogger(__name__)

class BackupManager:
    """
    ワールドデータのバックアップ管理を行うクラス
    """
    def __init__(self, config):
        self.config = config

    def _get_saved_dir(self) -> str:
        """保存データのディレクトリパスを取得する。"""
        server_path = self.config.get("server_path")
        return os.path.join(server_path, "Pal", "Saved")

    def _get_backup_dir(self) -> str:
        """バックアップ保存先のディレクトリパスを取得する。"""
        return self.config.get("backup_path")

    def create_backup(self) -> dict:
        """ワールドデータのバックアップを作成する。"""
        saved_dir = self._get_saved_dir()
        backup_dir = self._get_backup_dir()

        if not os.path.exists(saved_dir):
            logger.warning(f"保存データディレクトリが存在しません: {saved_dir}")
            return None

        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"palworld_backup_{timestamp}.tar.gz"
        backup_path = os.path.join(backup_dir, filename)

        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(saved_dir, arcname=os.path.basename(saved_dir))
            
            logger.info(f"バックアップを作成しました: {backup_path}")
            
            # 古いバックアップのクリーンアップ
            self.cleanup_old_backups()
            
            size = os.path.getsize(backup_path)
            return {
                "filename": filename,
                "size": size,
                "created_at": timestamp
            }
            
        except Exception as e:
            logger.error(f"バックアップ作成エラー: {e}")
            if os.path.exists(backup_path):
                os.remove(backup_path)
            return None

    def list_backups(self) -> list:
        """バックアップ一覧を取得する。"""
        backup_dir = self._get_backup_dir()
        if not os.path.exists(backup_dir):
            return []

        backups = []
        pattern = os.path.join(backup_dir, "palworld_backup_*.tar.gz")
        for filepath in glob.glob(pattern):
            try:
                filename = os.path.basename(filepath)
                size = os.path.getsize(filepath)
                # ファイル名からタイムスタンプを抽出
                timestamp_str = filename.replace("palworld_backup_", "").replace(".tar.gz", "")
                
                backups.append({
                    "filename": filename,
                    "size": size,
                    "created_at": timestamp_str,
                    "filepath": filepath
                })
            except Exception as e:
                logger.error(f"バックアップ情報の取得エラー ({filepath}): {e}")

        # 新しい順にソート
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups

    def restore_backup(self, filename: str) -> bool:
        """バックアップから復元する。※サーバー停止中のみ実行可能とする想定"""
        backup_dir = self._get_backup_dir()
        backup_path = os.path.join(backup_dir, filename)
        
        if not os.path.exists(backup_path):
            logger.error(f"バックアップファイルが見つかりません: {backup_path}")
            return False

        saved_dir = self._get_saved_dir()
        parent_dir = os.path.dirname(saved_dir)

        try:
            # 既存のSavedディレクトリを退避（安全のため）
            if os.path.exists(saved_dir):
                temp_backup = f"{saved_dir}_temp_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                shutil.move(saved_dir, temp_backup)
                logger.info(f"既存データを退避しました: {temp_backup}")

            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(path=parent_dir)
                
            logger.info(f"バックアップから復元しました: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"復元エラー: {e}")
            return False

    def delete_backup(self, filename: str) -> bool:
        """指定したバックアップを削除する。"""
        backup_dir = self._get_backup_dir()
        backup_path = os.path.join(backup_dir, filename)
        
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
                logger.info(f"バックアップを削除しました: {backup_path}")
                return True
            except Exception as e:
                logger.error(f"バックアップ削除エラー: {e}")
                return False
        return False

    def cleanup_old_backups(self):
        """設定された最大数を超えた古いバックアップを削除する。"""
        max_backups = self.config.get("max_backups", 10)
        if max_backups <= 0:
            return  # 0以下の場合は無制限とみなす
            
        backups = self.list_backups()
        if len(backups) > max_backups:
            to_delete = backups[max_backups:]
            for backup in to_delete:
                self.delete_backup(backup["filename"])
