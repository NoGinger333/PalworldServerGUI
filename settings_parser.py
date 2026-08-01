import os
import re
import logging

logger = logging.getLogger(__name__)

class PalWorldSettings:
    """
    PalWorldSettings.ini のパースと書き込みを行うクラス
    """
    def __init__(self, file_path):
        self.file_path = file_path
        self.header = "[/Script/Pal.PalGameWorldSettings]"
        self.option_prefix = "OptionSettings=("
        self.option_suffix = ")"

    def load(self) -> dict:
        """設定ファイルを読み込んで辞書として返す。"""
        settings_dict = self.get_default_settings()
        
        if not os.path.exists(self.file_path):
            logger.info(f"設定ファイルが存在しません: {self.file_path}")
            return settings_dict

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # OptionSettings=(...) の中身を抽出
            match = re.search(r'OptionSettings=\((.*)\)', content, re.DOTALL)
            if not match:
                logger.warning("設定フォーマットが正しくありません。")
                return settings_dict

            options_str = match.group(1)
            
            # カンマで分割するが、クォーテーション内のカンマを考慮する簡易的な正規表現
            # 実際の設定値には文字列内にカンマが含まれることはほぼない
            pairs = options_str.split(',')
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"')
                    
                    # 既存のキーであれば値を更新（型変換はここでは行わず文字列で保持）
                    if key in settings_dict:
                        settings_dict[key] = value
                    else:
                        settings_dict[key] = value

            return settings_dict

        except Exception as e:
            logger.error(f"設定ファイルの読み込みエラー: {e}")
            return settings_dict

    def save(self, settings_dict: dict):
        """辞書から設定ファイルに書き込む。"""
        try:
            # ディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

            options_list = []
            for key, val in settings_dict.items():
                # 文字列型の場合はダブルクォートで囲む必要がある（一部例外あり）
                # メタデータから型を判定するのが確実だが、簡易的に対応
                meta = next((m for m in self.get_settings_metadata() if m['key'] == key), None)
                if meta and meta['type'] == 'string' and val:
                    options_list.append(f'{key}="{val}"')
                else:
                    # Bool値の変換 (Python の True/False から文字列へ)
                    if isinstance(val, bool):
                        val = "True" if val else "False"
                    options_list.append(f'{key}={val}')

            options_str = ",".join(options_list)
            content = f"{self.header}\n{self.option_prefix}{options_str}{self.option_suffix}\n"

            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            logger.info(f"設定ファイルを保存しました: {self.file_path}")
            
        except Exception as e:
            logger.error(f"設定ファイルの保存エラー: {e}")
            raise e

    def get_default_settings(self) -> dict:
        """全設定のデフォルト値を返す。"""
        defaults = {}
        for meta in self.get_settings_metadata():
            defaults[meta['key']] = meta['default']
        return defaults

    def get_settings_metadata(self) -> list:
        """各設定のメタデータを返す。"""
        return [
            # Server
            {'key': 'ServerName', 'label': 'サーバー名', 'type': 'string', 'default': 'Default Palworld Server', 'category': 'server', 'description': 'サーバーの表示名'},
            {'key': 'ServerDescription', 'label': 'サーバー説明', 'type': 'string', 'default': '', 'category': 'server', 'description': 'サーバーの説明文'},
            {'key': 'AdminPassword', 'label': '管理者パスワード', 'type': 'string', 'default': '', 'category': 'server', 'description': '管理者のパスワード'},
            {'key': 'ServerPassword', 'label': 'サーバーパスワード', 'type': 'string', 'default': '', 'category': 'server', 'description': 'サーバーへの接続パスワード'},
            {'key': 'ServerPlayerMaxNum', 'label': '最大プレイヤー数', 'type': 'int', 'default': '32', 'category': 'server', 'description': '最大同時接続人数', 'min': 1, 'max': 32},
            {'key': 'PublicPort', 'label': '公開ポート', 'type': 'int', 'default': '8211', 'category': 'server', 'description': 'サーバーの公開ポート'},
            {'key': 'PublicIP', 'label': '公開IP', 'type': 'string', 'default': '', 'category': 'server', 'description': 'サーバーの公開IPアドレス'},
            {'key': 'RCONEnabled', 'label': 'RCON有効', 'type': 'bool', 'default': 'False', 'category': 'server', 'description': 'RCON機能を有効にするか'},
            {'key': 'RCONPort', 'label': 'RCONポート', 'type': 'int', 'default': '25575', 'category': 'server', 'description': 'RCONのポート番号'},
            
            # Rates
            {'key': 'ExpRate', 'label': '経験値倍率', 'type': 'float', 'default': '1.000000', 'category': 'rates', 'description': '獲得経験値の倍率'},
            {'key': 'PalCaptureRate', 'label': 'パル捕獲確率倍率', 'type': 'float', 'default': '1.000000', 'category': 'rates', 'description': 'パルを捕獲する確率の倍率'},
            {'key': 'PalSpawnNumRate', 'label': 'パル出現数倍率', 'type': 'float', 'default': '1.000000', 'category': 'rates', 'description': 'パルの出現数の倍率'},
            {'key': 'DamageRatePlayerToEnemy', 'label': 'プレイヤー与ダメージ倍率', 'type': 'float', 'default': '1.000000', 'category': 'rates', 'description': 'プレイヤーから敵へのダメージ倍率'},
            {'key': 'DamageRateEnemyToPlayer', 'label': '敵からプレイヤーへの被ダメージ倍率', 'type': 'float', 'default': '1.000000', 'category': 'rates', 'description': '敵からプレイヤーへのダメージ倍率'},
            {'key': 'MiningDamageRate', 'label': '採掘ダメージ倍率', 'type': 'float', 'default': '1.000000', 'category': 'rates', 'description': '採掘のダメージ倍率'},
            {'key': 'CollectionDropRate', 'label': '採取アイテムドロップ倍率', 'type': 'float', 'default': '1.000000', 'category': 'rates', 'description': '採取時のアイテムドロップ倍率'},
            {'key': 'CollectionObjectHpRate', 'label': '採取オブジェクトHP倍率', 'type': 'float', 'default': '1.000000', 'category': 'rates', 'description': '採取オブジェクトのHP倍率'},
            {'key': 'EnemyDropItemRate', 'label': '敵ドロップアイテム倍率', 'type': 'float', 'default': '1.000000', 'category': 'rates', 'description': '敵を倒した際のアイテムドロップ倍率'},
            
            # Gameplay
            {'key': 'DeathPenalty', 'label': 'デスペナルティ', 'type': 'enum', 'default': 'All', 'category': 'gameplay', 'description': '死亡時のペナルティ', 'options': ['None', 'Item', 'ItemAndEquipment', 'All']},
            {'key': 'bEnablePlayerToPlayerDamage', 'label': 'プレイヤー間ダメージ', 'type': 'bool', 'default': 'False', 'category': 'gameplay', 'description': 'PvPダメージを有効にするか'},
            {'key': 'bEnableFriendlyFire', 'label': 'フレンドリーファイア', 'type': 'bool', 'default': 'False', 'category': 'gameplay', 'description': '味方へのダメージを有効にするか'},
            {'key': 'bEnableInvaderEnemy', 'label': '襲撃イベント', 'type': 'bool', 'default': 'True', 'category': 'gameplay', 'description': '拠点への襲撃イベントを有効にするか'},
            {'key': 'bActiveUNKO', 'label': 'ウンコ生成', 'type': 'bool', 'default': 'True', 'category': 'gameplay', 'description': 'パルのウンコ生成を有効にするか'},
            {'key': 'bEnableAimAssistPad', 'label': 'エイムアシスト(パッド)', 'type': 'bool', 'default': 'True', 'category': 'gameplay', 'description': 'パッドのエイムアシストを有効にするか'},
            {'key': 'bEnableAimAssistKeyboard', 'label': 'エイムアシスト(キーボード)', 'type': 'bool', 'default': 'False', 'category': 'gameplay', 'description': 'キーボードのエイムアシストを有効にするか'},
            
            # Environment
            {'key': 'DayTimeSpeedRate', 'label': '昼の進行速度倍率', 'type': 'float', 'default': '1.000000', 'category': 'environment', 'description': '昼の時間の進む速さ'},
            {'key': 'NightTimeSpeedRate', 'label': '夜の進行速度倍率', 'type': 'float', 'default': '1.000000', 'category': 'environment', 'description': '夜の時間の進む速さ'},
            {'key': 'PalEggDefaultHatchingTime', 'label': 'キョダイタマゴ孵化時間(h)', 'type': 'float', 'default': '72.000000', 'category': 'environment', 'description': '巨大卵の孵化にかかる時間'},
            {'key': 'BaseCampWorkerMaxNum', 'label': '拠点作業パル最大数', 'type': 'int', 'default': '15', 'category': 'environment', 'description': '拠点で作業できるパルの最大数'},
            
            # Advanced
            {'key': 'bIsMultiplay', 'label': 'マルチプレイ', 'type': 'bool', 'default': 'False', 'category': 'advanced', 'description': 'マルチプレイを有効にするか'},
            {'key': 'bIsPvP', 'label': 'PvP有効', 'type': 'bool', 'default': 'False', 'category': 'advanced', 'description': 'PvPを有効にするか'},
            {'key': 'CoopPlayerMaxNum', 'label': 'Coop最大プレイヤー数', 'type': 'int', 'default': '4', 'category': 'advanced', 'description': 'Coopモードの最大人数'},
            {'key': 'AutoSaveSpan', 'label': 'オートセーブ間隔(秒)', 'type': 'float', 'default': '30.000000', 'category': 'advanced', 'description': 'オートセーブを行う間隔'},
            {'key': 'bIsUseBackupSaveData', 'label': 'バックアップセーブ使用', 'type': 'bool', 'default': 'True', 'category': 'advanced', 'description': 'バックアップセーブデータを使用するか'},
            
            # Default required items that might not be in UI explicitly but needed
            {'key': 'Difficulty', 'label': '難易度', 'type': 'enum', 'default': 'None', 'category': 'hidden', 'description': '', 'options': ['None', 'Easy', 'Normal', 'Hard']}
        ]
