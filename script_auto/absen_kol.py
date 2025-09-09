#!/usr/bin/env python3
import os
import sys
import json
import time
import requests

# === ENV variables (dari GitHub Actions secrets) ===
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DATE_HEADER_TEXT = os.getenv('ABSENSI_DATE_HEADER', '15 AGUSTUS 2025')

def send_telegram_message(chat_id, message):
    """Kirim pesan via Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, data={"chat_id": chat_id, "text": message})
        print("Telegram response:", resp.json())
    except Exception as e:
        print("Telegram error:", e)

def absen_user(telegram_id, username, password, mode):
    """Dummy absen (asli bisa diganti logic Selenium)"""
    print(f"Mulai absen {mode} untuk {username} ({telegram_id})")
    send_telegram_message(telegram_id, f"✅ Absen {mode} untuk {username} berhasil (simulasi).")
    time.sleep(2)
    print(f"Selesai absen {mode} untuk {username} ({telegram_id})")

def main():
    if len(sys.argv) < 3:
        print("Usage: python absen_kol.py '<json_users>' <pagi|sore>")
        sys.exit(1)

    try:
        users = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print("❌ Gagal parse JSON:", e)
        sys.exit(1)

    mode = sys.argv[2].lower()
    if mode not in ["pagi", "sore"]:
        print("❌ Mode harus 'pagi' atau 'sore'")
        sys.exit(1)

    print(f"Menjalankan absen {mode} untuk {len(users)} pengguna...")

    for user in users:
        if len(user) != 3:
            print("❌ Format user salah, harus [telegram_id, username, password]")
            continue
        telegram_id, username, password = user
        absen_user(telegram_id, username, password, mode)

if __name__ == "__main__":
    main()
