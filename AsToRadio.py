#!/usr/bin/env python3
import socket
import struct
import threading
import time
import sys
import serial
import alsaaudio

# **設定値類**
# IPアドレスとポート
# セキュリティが無いので同一サーバ以外での動作は非推奨
# LISTEN_IP = '0.0.0.0'
LISTEN_IP = '127.0.0.1'
LISTEN_PORT = 9092

# オーディオデバイス
AUDIO_DEV = f"plughw:1,0"

# PTT制御用シリアルポート(RTSピン制御)
SERIAL_PORT = "/dev/ttyUSB0" 
# あるいは明示指定する(要書き換え)
# SERIAL_PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_98cdcf305587ed11a7322ed7a603910e-if00-port0"

# Audio Settings
AST_RATE = 8000
CHANNELS = 1
FORMAT = alsaaudio.PCM_FORMAT_S16_LE
PERIOD_SIZE = 160 

# PTT Logic
TX_DELAY = 0.1
# DTMFの連打防止時間（秒）
DTMF_DEBOUNCE_TIME = 0.3

# Protocol Constants
TYPE_HANGUP = 0x00
TYPE_UUID   = 0x01
TYPE_DTMF   = 0x03
TYPE_SOUND  = 0x10

class RadioServer:
    def __init__(self):
        self.server_sock = None
        self.inp = None
        self.out = None
        self.ser = None
        self.conn = None
        self.client_connected = False
        self.ptt_active = False
        
        self.lock = threading.RLock()
        
        # DTMFチャタリング防止用
        self.last_dtmf_time = 0

    def setup_serial(self):
        try:
            self.ser = serial.Serial(SERIAL_PORT, baudrate=9600, rtscts=False, dsrdtr=False)
            self.ser.rts = False
            print(f"Serial: Opened {SERIAL_PORT}")
            return True
        except Exception as e:
            print(f"Serial Error: {e}")
            return False

    def set_ptt(self, state):
        with self.lock:
            if self.ptt_active != state:
                self.ptt_active = state
                if self.ser:
                    self.ser.rts = state
                
                status = "ON (TX)" if state else "OFF (RX)"
                # PTTトグル確認用
                # print(f"PTT Changed: {status}")
                
                if state:
                    time.sleep(TX_DELAY)

    def toggle_ptt(self):
        """ PTTの状態を反転させる """
        with self.lock:
            # 現在の状態を反転させてセット
            new_state = not self.ptt_active
            self.set_ptt(new_state)

    def open_audio_device(self):

        dev_name = AUDIO_DEV

        try:
            self.inp = alsaaudio.PCM(
                type=alsaaudio.PCM_CAPTURE, mode=alsaaudio.PCM_NORMAL, device=dev_name,
                channels=CHANNELS, rate=AST_RATE, format=FORMAT, periodsize=PERIOD_SIZE
            )
            self.out = alsaaudio.PCM(
                type=alsaaudio.PCM_PLAYBACK, mode=alsaaudio.PCM_NORMAL, device=dev_name,
                channels=CHANNELS, rate=AST_RATE, format=FORMAT, periodsize=PERIOD_SIZE
            )
            # print(f"Audio: Opened {dev_name} (8kHz)")
            return True
        except Exception as e:
            print(f"Audio Open Failed: {e}")
            self.close_audio_device()
            return False

    def close_audio_device(self):
        if self.inp: self.inp.close(); self.inp = None
        if self.out: self.out.close(); self.out = None

    def tx_loop(self):
        while self.client_connected:
            try:
                # PTT ON(送信中)は、無線機からの音声を拾わない（ループバック防止）
                if self.ptt_active:
                    time.sleep(0.02)
                    continue

                if self.inp:
                    length, data = self.inp.read()
                    if length > 0:
                        header = struct.pack('!BH', TYPE_SOUND, len(data))
                        self.conn.sendall(header + data)
            except Exception:
                break

    def handle_client(self, conn, addr):
        print(f"Connection from {addr}")
        self.conn = conn
        self.client_connected = True
        
        if not self.open_audio_device():
            conn.close()
            return

        tx_thread = threading.Thread(target=self.tx_loop)
        tx_thread.start()

        try:
            while self.client_connected:
                header = conn.recv(3)
                if not header or len(header) < 3: break
                msg_type, length = struct.unpack('!BH', header)
                
                payload = b''
                while len(payload) < length:
                    packet = conn.recv(length - len(payload))
                    if not packet: raise Exception("Closed")
                    payload += packet
                
                if msg_type == TYPE_SOUND:
                    # PTTがONのときだけ、無線機に音声を流す
                    if self.ptt_active and self.out:
                        self.out.write(payload)

                elif msg_type == TYPE_DTMF:
                    digit = payload.decode('utf-8', errors='ignore')
                    
                    if digit == '*':
                        # チャタリング防止（0.3秒以内の連打は無視）
                        now = time.time()
                        if now - self.last_dtmf_time > DTMF_DEBOUNCE_TIME:
                            # DTMF確認用
                            # print(f"DTMF: {digit} (Toggle PTT)")
                            self.toggle_ptt()
                            self.last_dtmf_time = now
                        else:
                            # デバッグ用
                            # print(f"DTMF: {digit} (Ignored - Debounce)")
                            pass

                elif msg_type == TYPE_HANGUP:
                    print("Hangup received")
                    break

        except Exception as e:
            print(f"Connection Error: {e}")
        finally:
            self.client_connected = False
            self.set_ptt(False) # 切断時はOFF
            self.close_audio_device()
            try: conn.close()
            except: pass
            tx_thread.join()
            print("Disconnected")

    def start_server(self):
        if not self.setup_serial(): return

        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind((LISTEN_IP, LISTEN_PORT))
            self.server_sock.listen(1)
            print(f"Radio Gateway Listening on {LISTEN_IP}:{LISTEN_PORT}")

            while True:
                conn, addr = self.server_sock.accept()
                self.handle_client(conn, addr)

        except KeyboardInterrupt:
            pass
        finally:
            if self.server_sock: self.server_sock.close()

if __name__ == '__main__':
    server = RadioServer()
    server.start_server()
