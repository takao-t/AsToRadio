#!/usr/bin/env python3
import alsaaudio

print("--- ALSA Sound Cards ---")
# alsaaudio.cards() は [カード名, カード名, ...] のリストを返します
# リストのインデックス番号がそのまま ALSAのカード番号(hw:X) になります
card_list = alsaaudio.cards()

if not card_list:
    print("No sound cards found.")
else:
    for idx, name in enumerate(card_list):
        print(f"Card {idx}: {name}")

print("\n--- Note ---")
print("上記の 'Card X' の番号を使って 'plughw:X,0' と指定します。")
print("例: Card 1 が Digirig なら、デバイス名は 'plughw:1,0' です。")
print("    DigiRigの場合、単純に Device と表示されます。")
