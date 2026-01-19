# Asterisk AudioSocket Radio Gateway

Debian 13 (Trixie) 上で動作する、Asterisk と無線機（Digirig Mobile経由）を接続するためのゲートウェイシステムです。 Python標準の alsa-audio ライブラリを使用し、AudioSocketプロトコルを通じて音声の送受信とPTT制御を行います。

## システム要件
OS: Debian 13 (Trixie) 以降

ハードウェア: Digirig Mobile (または CM108系オーディオ + CP2102系シリアル 複合デバイス)、あるいはオーディオIFとUSBシリアル等。ここではDigirig Mobileを使用しています。

ソフトウェア: Asterisk (AudioSocketで通信します)

## インストール手順

必要なパッケージの導入

仮想環境(venv)は使用せず、システム標準のパッケージを使用します。

```
sudo apt update
sudo apt install python3-serial python3-alsaaudio
```

## ユーザー権限の設定
スクリプトを実行するユーザー（asteriskと仮定）には、シリアルポートとオーディオデバイスへのアクセス権限が必要です。

```
sudo usermod -aG dialout,audio $USER
```

## デバイスの確認

### オーディオデバイス

添付のlist_dev.pyを実行するとオーディオデバイスの一覧が表示されます。
```
# python3 ./list_dev.py
--- ALSA Sound Cards ---
Card 0: PCH
Card 1: Device

--- Note ---
上記の 'Card X' の番号を使って 'plughw:X,0' と指定します。
例: Card 1 が Digirig なら、デバイス名は 'plughw:1,0' です。
    DigiRigの場合、単純に Device と表示されます。
```
DigiRgiの場合、単に"Device"と表示されることが多いようです。上記の例ならばデバイスのインデックスは"1"となります。これを AsToRadio.pyの以下の個所に設定します。

```
# オーディオデバイス
AUDIO_DEV = f"plughw:1,0"
```

### シリアルポート
DigiRigのシリアルポートを確認して設定してください。/dev/ttyUSB0のようなかたちですが、抜き差しで変わって困るという場合には by-id の方を使ってください。

```
# PTT制御用シリアルポート(RTSピン制御)
SERIAL_PORT = "/dev/ttyUSB0"
# あるいは明示指定する(要書き換え)
# SERIAL_PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_98cdcf305587ed11a7322ed7a603910e-if00-port0"
```

## ファイルの配置

```
cp AsToRadio.py /usr/local/bin/.
chmod +x /usr/local/bin/AsToRadio.py
```

デーモン起動するためにsystemdのUnitファイルをコピーします。なお、実行ユーザ/グループは"asterisk"になっていますので、異なるユーザ/グループで実行したい場合には書き換えてください。

```
cp AsToRadio.service /etc/systemd/system/.
systemctl daemon-reload
systemctl enable AsToRadio
```

これでsystemctl start AsToRadioで起動するはずです。なおデーモン化する前にフォアグラウンド起動してみたい場合には単純に python3 ./AsToRadio.py で実行してみてください。

## Asteriskからの使用

```
exten => 7000,1,NoOp
exten => 7000,n,Answer()
exten => 7000,n,Set(MYUUID=${UUID()})
exten => 7000,n,Audiosocket(${MYUUID},127.0.0.1:9092)
exten => 7000,n,Hangup
```

上記の例のようにAudioscoket()でこのゲートウェイに対して接続します。接続されると「無線空間」の音が聞こえるはずです。送信したい場合にはDTMFで'*'を押してから喋ってください。再び受信に戻るには'*'をもう一度押します。なお、接続している電話機等が切断するとPTTは自動的にオフになります。
