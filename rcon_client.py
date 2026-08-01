import socket
import struct
import logging

logger = logging.getLogger(__name__)

# パケットタイプ定数
SERVERDATA_AUTH = 3
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_RESPONSE_VALUE = 0

class RconAuthError(Exception):
    pass

class RconError(Exception):
    pass

class RconClient:
    """
    Source RCON プロトコルのPython実装
    外部ライブラリに依存せず、TCPソケット通信でRCONコマンドを実行する。
    """
    def __init__(self, host, port, password):
        self.host = host
        self.port = int(port)
        self.password = password
        self.socket = None
        self.request_id_counter = 1

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        """サーバーに接続し、認証を行う。"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))
            
            # 認証パケット送信
            req_id, resp = self._send_packet(SERVERDATA_AUTH, self.password)
            
            # 認証レスポンスの確認
            # 最初のレスポンスがRESPONSE_VALUE(空)の場合があるため、AUTH_RESPONSEを待つ
            auth_resp_id = None
            for _ in range(2):
                resp_id, packet_type, payload = self._read_packet()
                if packet_type == SERVERDATA_AUTH_RESPONSE:
                    auth_resp_id = resp_id
                    break
            
            if auth_resp_id == -1:
                raise RconAuthError("RCON認証に失敗しました。パスワードが間違っています。")
            
            logger.info(f"RCON接続成功: {self.host}:{self.port}")
            
        except Exception as e:
            self.disconnect()
            raise RconError(f"RCON接続エラー: {e}")

    def disconnect(self):
        """サーバーとの接続を切断する。"""
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def send_command(self, command: str) -> str:
        """コマンドを送信し、レスポンスを返す。"""
        if not self.socket:
            raise RconError("ソケットが接続されていません。")
        
        try:
            req_id, _ = self._send_packet(SERVERDATA_EXECCOMMAND, command)
            
            # レスポンスの読み取り
            resp_id, packet_type, payload = self._read_packet()
            
            if resp_id != req_id:
                logger.warning("RCONリクエストIDが一致しません。")
                
            return payload
            
        except Exception as e:
            self.disconnect()
            raise RconError(f"コマンド送信エラー: {e}")

    def _send_packet(self, packet_type: int, payload: str):
        """パケットを構築して送信する。"""
        req_id = self.request_id_counter
        self.request_id_counter += 1
        
        # payloadはnull終端
        encoded_payload = payload.encode('utf-8') + b'\x00'
        # 最後にさらに1バイトのnullパディングが必要
        packet_body = struct.pack('<ii', req_id, packet_type) + encoded_payload + b'\x00'
        
        # sizeは req_id(4) + packet_type(4) + payload_len + 1
        packet_size = len(packet_body)
        packet = struct.pack('<i', packet_size) + packet_body
        
        self.socket.sendall(packet)
        return req_id, packet

    def _read_packet(self):
        """レスポンスパケットを読み取る。"""
        # サイズ(4バイト)の読み取り
        size_data = self._recv_exact(4)
        if not size_data:
            raise RconError("パケットサイズの読み取りに失敗しました。")
            
        packet_size = struct.unpack('<i', size_data)[0]
        
        # 残りのデータの読み取り
        packet_data = self._recv_exact(packet_size)
        if len(packet_data) < 8:
            raise RconError("パケットデータが短すぎます。")
            
        req_id, packet_type = struct.unpack('<ii', packet_data[:8])
        # 最後の2バイトはnullパディング (payloadはnull終端 + null)
        payload = packet_data[8:-2].decode('utf-8', errors='replace')
        
        return req_id, packet_type, payload

    def _recv_exact(self, length: int) -> bytes:
        """指定した長さのデータを正確に読み取る。"""
        data = b''
        while len(data) < length:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                break
            data += chunk
        return data
