#!/usr/bin/env python3
import os
import sys
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
import stat
import base64

# === ENV variables (isi dari GitHub Secrets nanti) ===
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DATE_HEADER_TEXT = os.getenv('ABSENSI_DATE_HEADER', '15 AGUSTUS 2025')

# === Fungsi kirim Telegram ===
def send_telegram_message(chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, data={"chat_id": chat_id, "text": message})
        if resp.status_code != 200:
            print(f"❌ Gagal kirim pesan ke {chat_id}: {resp.text}")
    except Exception as e:
        print("Telegram error:", e)

def send_telegram_photo(chat_id, photo_path):
    try:
        with open(photo_path, 'rb') as photo:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            resp = requests.post(url, data={"chat_id": chat_id}, files={"photo": photo})
            return resp.status_code == 200
    except Exception as e:
        print("Telegram photo error:", e)
        return False

# === Setup Selenium Chrome ===
chrome_options = Options()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--headless=new')
chrome_options.add_argument('--window-size=1920,1080')

def click_element_safely(driver, element):
    try:
        element.click()
        return True
    except ElementClickInterceptedException:
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            return False
    except Exception:
        return False

# === Logic absen user ===
def absen_user(telegram_id, username, password, mode):
    driver = None
    try:
        send_telegram_message(telegram_id, f"🔄 Mulai absen {mode} untuk {username}...")

        driver_path = ChromeDriverManager().install()
        if "THIRD_PARTY_NOTICES" in driver_path:
            driver_dir = os.path.dirname(driver_path)
            for file in os.listdir(driver_dir):
                if file.startswith("chromedriver") and not file.endswith(".chromedriver"):
                    driver_path = os.path.join(driver_dir, file)
                    break
        if os.path.exists(driver_path):
            st = os.stat(driver_path)
            os.chmod(driver_path, st.st_mode | stat.S_IEXEC)

        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get('https://kolabjar-asnpintar.lan.go.id/login')
        time.sleep(2)

        # login
        driver.find_element(By.NAME, 'username').send_keys(username)
        driver.find_element(By.NAME, 'password').send_keys(password)
        driver.find_element(By.XPATH, '//button[@type="submit"]').click()
        time.sleep(5)

        send_telegram_message(telegram_id, f"✅ Login berhasil untuk {username}")

        # TODO: tambahkan langkah navigasi absensi sesuai logic aslinya
        send_telegram_message(telegram_id, f"✅ Absen {mode} berhasil (dummy).")

        return True
    except Exception as e:
        send_telegram_message(telegram_id, f"❌ Absen {mode} gagal: {e}")
        return False
    finally:
        if driver:
            driver.quit()
            print("Browser ditutup.")
        send_telegram_message(telegram_id, f"🏁 Proses absen {mode} selesai.")

# === Main ===
def main():
    if len(sys.argv) < 3:
        print("Usage: python absen_kol.py '<json_users>' <pagi|sore>")
        print("Contoh: python absen_kol.py '[ [\"123\",\"user1\",\"pass1\"], [\"456\",\"user2\",\"pass2\"] ]' pagi")
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
            print("❌ Format user salah:", user)
            continue
        telegram_id, username, password = user
        absen_user(telegram_id, username, password, mode)
        time.sleep(3)

if __name__ == "__main__":
    main()
