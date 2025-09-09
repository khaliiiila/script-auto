#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException
import time
import stat
import requests
import base64
from database import get_all_users

# Load environment variables
load_dotenv()

# Get configuration from environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DATE_HEADER_TEXT = os.getenv('ABSENSI_DATE_HEADER', '15 AGUSTUS 2025')

def send_telegram_message(chat_id, message):
    """Send a text message via Telegram"""
    try:
        telegram_url = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN)
        data = {
            'chat_id': chat_id,
            'text': message
        }
        response = requests.post(telegram_url, data=data)
        
        if response.status_code == 200:
            print("Message sent via Telegram successfully to {}!".format(chat_id))
        else:
            print("Failed to send message via Telegram to {}. Status code: {}".format(chat_id, response.status_code))
    except Exception as telegram_error:
        print("Error sending message via Telegram to {}: {}".format(chat_id, telegram_error))

def send_telegram_photo(chat_id, photo_path):
    """Send a photo via Telegram"""
    try:
        with open(photo_path, 'rb') as photo:
            telegram_url = "https://api.telegram.org/bot{}/sendPhoto".format(TELEGRAM_BOT_TOKEN)
            data = {'chat_id': chat_id}
            files = {'photo': photo}
            response = requests.post(telegram_url, data=data, files=files)
            
            if response.status_code == 200:
                print("Photo sent via Telegram successfully to {}!".format(chat_id))
                return True
            else:
                print("Failed to send photo via Telegram to {}. Status code: {}".format(chat_id, response.status_code))
                return False
    except Exception as telegram_error:
        print("Error sending photo via Telegram to {}: {}".format(chat_id, telegram_error))
        return False

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--start-maximized')  # Maximize window for better screenshot
chrome_options.add_argument('--headless=new')  # Run headless
chrome_options.add_argument('--window-size=1920,1080')

def screenshot_between_comments(driver, start_comment, end_comment, out_path):
    """Capture screenshot of the region between two HTML comment markers.

    This uses JS to locate comment nodes and compute a union bounding box
    of elements between them, then Chrome DevTools to capture a clipped
    screenshot of that rectangle.
    """
    try:
        driver.execute_script("window.scrollTo(0,0);")
        box = driver.execute_script(
            """
            return (function(startText, endText){
                const it = document.createNodeIterator(document.documentElement, NodeFilter.SHOW_ALL);
                let n, started = false;
                const els = [];
                while ((n = it.nextNode())) {
                    if (n.nodeType === Node.COMMENT_NODE) {
                        const t = (n.nodeValue || '').trim();
                        if (!started && t.includes(startText)) { started = true; continue; }
                        if (started && t.includes(endText)) { break; }
                    } else if (started && n.nodeType === Node.ELEMENT_NODE) {
                        els.push(n);
                    }
                }
                if (!started || els.length === 0) return null;
                let rect = null;
                for (const el of els) {
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 && r.height === 0) continue;
                    if (!rect) rect = {left:r.left, top:r.top, right:r.right, bottom:r.bottom};
                    else {
                        rect.left = Math.min(rect.left, r.left);
                        rect.top = Math.min(rect.top, r.top);
                        rect.right = Math.max(rect.right, r.right);
                        rect.bottom = Math.max(rect.bottom, r.bottom);
                    }
                }
                if (!rect) return null;
                const x = Math.max(0, rect.left + window.scrollX);
                const y = Math.max(0, rect.top + window.scrollY);
                const width = Math.max(0, rect.right - rect.left);
                const height = Math.max(0, rect.bottom - rect.top);
                return {x, y, width, height, dpr: window.devicePixelRatio};
            })(arguments[0], arguments[1]);
            """,
            start_comment,
            end_comment,
        )
        if not box or box.get("width", 0) == 0 or box.get("height", 0) == 0:
            return False
        clip = {
            "x": float(box["x"]),
            "y": float(box["y"]),
            "width": float(box["width"]),
            "height": float(box["height"]),
            "scale": 1,
        }
        # Use Chrome DevTools to capture a clipped screenshot beyond viewport
        png_b64 = driver.execute_cdp_cmd(
            'Page.captureScreenshot',
            {
                'format': 'png',
                'clip': clip,
                'captureBeyondViewport': True,
                'fromSurface': True,
            }
        ).get('data')
        if not png_b64:
            return False
        with open(out_path, 'wb') as f:
            f.write(base64.b64decode(png_b64))
        return True
    except Exception:
        return False

def screenshot_first_element_by_css(driver, selector, out_path):
    """Capture a clipped screenshot of the first element matching CSS selector.

    Uses Chrome DevTools to capture the exact bounding box even if the element
    is larger than the viewport.
    """
    try:
        driver.execute_script("window.scrollTo(0,0);")
        box = driver.execute_script(
            """
            const el = document.querySelector(arguments[0]);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            const x = Math.max(0, r.left + window.scrollX);
            const y = Math.max(0, r.top + window.scrollY);
            const width = Math.max(0, r.right - r.left);
            const height = Math.max(0, r.bottom - r.top);
            return {x, y, width, height, dpr: window.devicePixelRatio};
            """,
            selector,
        )
        if not box or box.get("width", 0) == 0 or box.get("height", 0) == 0:
            return False
        clip = {
            "x": float(box["x"]),
            "y": float(box["y"]),
            "width": float(box["width"]),
            "height": float(box["height"]),
            "scale": 1,
        }
        png_b64 = driver.execute_cdp_cmd(
            'Page.captureScreenshot',
            {
                'format': 'png',
                'clip': clip,
                'captureBeyondViewport': True,
                'fromSurface': True,
            }
        ).get('data')
        if not png_b64:
            return False
        with open(out_path, 'wb') as f:
            f.write(base64.b64decode(png_b64))
        return True
    except Exception:
        return False

def scroll_to_date_header(driver, date_text):
    """Scroll the container that contains a TH[colspan="2"] with given date text to the bottom.

    Returns True if the date header is found and scrolled; False otherwise.
    """
    try:
        # Wait briefly for table to render
        time.sleep(1)
        xpath = "//th[@colspan='2' and normalize-space(.)='{}']".format(date_text)
        header = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        # Find the nearest scrollable ancestor (or fallback to document)
        scroll_ok = driver.execute_script(
            """
            const header = arguments[0];
            function findScrollable(el){
                let cur = el;
                while (cur) {
                    const cs = getComputedStyle(cur);
                    const oy = cs.overflowY;
                    if ((oy === 'auto' || oy === 'scroll') && cur.scrollHeight > cur.clientHeight) return cur;
                    cur = cur.parentElement;
                }
                return document.scrollingElement || document.documentElement;
            }
            const cont = findScrollable(header);
            header.scrollIntoView({block:'start'});
            cont.scrollTop = cont.scrollHeight;
            return true;
            """,
            header,
        )
        return bool(scroll_ok)
    except Exception:
        return False

def click_element_safely(driver, element):
    """Safely click an element, handling intercepted clicks"""
    try:
        # Try regular click first
        element.click()
        return True
    except ElementClickInterceptedException:
        # If click is intercepted, try JavaScript click
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as js_error:
            print("JavaScript click also failed: {}".format(js_error))
            return False
    except Exception as e:
        print("Regular click failed: {}".format(e))
        return False

def absen_user(telegram_id, username, password, mode):
    """Perform attendance (morning or afternoon) for a specific user"""
    driver = None
    absen_berhasil = False
    try:
        # Send start notification
        send_telegram_message(telegram_id, "🔄 Memulai proses absen {}...".format(mode))
        
        # Automatically download and set up ChromeDriver
        print("Mengunduh dan mengatur ChromeDriver...")
        driver_path = ChromeDriverManager().install()
        print("ChromeDriver path: {}".format(driver_path))
        
        # Fix for incorrect path selection
        if "THIRD_PARTY_NOTICES" in driver_path:
            # Get the directory containing the driver
            driver_dir = os.path.dirname(driver_path)
            # Look for the actual chromedriver executable
            for file in os.listdir(driver_dir):
                if file.startswith("chromedriver") and not file.endswith(".chromedriver"):
                    driver_path = os.path.join(driver_dir, file)
                    break
            print("Corrected ChromeDriver path: {}".format(driver_path))
        
        # Set executable permissions for the driver
        if os.path.exists(driver_path):
            st = os.stat(driver_path)
            os.chmod(driver_path, st.st_mode | stat.S_IEXEC)
            print("Set executable permissions for ChromeDriver")
        
        # Create service with the driver path
        service = Service(driver_path)
        
        # Initialize the Chrome driver
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Access the website
        print("Mengakses website login...")
        driver.get('https://kolabjar-asnpintar.lan.go.id/login')

        # Wait for the page to load
        time.sleep(3)

        # Find username and password fields and fill them
        print("Mengisi form login...")
        username_field = driver.find_element(By.NAME, 'username')
        password_field = driver.find_element(By.NAME, 'password')

        # Fill both fields with the specified value
        username_field.send_keys(username)
        password_field.send_keys(password)

        # Find and click the login button (assuming it's a submit button in a form)
        login_button = driver.find_element(By.XPATH, '//button[@type="submit"]')
        login_button.click()

        # Wait for login to complete and check if login was successful
        time.sleep(5)
        
        # Check if login was successful by looking for the widget-course-owner element
        try:
            course_owner_element = driver.find_element(By.CLASS_NAME, 'widget-course-owner')
            print("Login successful!")
            send_telegram_message(telegram_id, "✅ Login berhasil!")
            
            # Wait for the course-footer div to appear on the dashboard
            try:
                print("Menunggu elemen course-footer muncul di dashboard...")
                # Wait up to 15 seconds for the course-footer div to appear
                course_footer = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'course-footer'))
                )
                
                # Find and click the "Detail" button within the course-footer div
                # Using the correct XPath based on the provided HTML structure
                detail_button = course_footer.find_element(By.XPATH, './/a[contains(@class, "btn-detail")]')
                print("Elemen course-footer ditemukan, mengklik tombol Detail...")
                detail_button.click()
                time.sleep(3)
                
                # Get and display the current URL after clicking Detail
                current_url = driver.current_url
                print("URL setelah klik Detail: {}".format(current_url))
                # send_telegram_message(telegram_id, "🔗 URL setelah klik Detail: {}".format(current_url))
                
                # Extract course ID from URL
                # URL format: https://kolabjar-asnpintar.lan.go.id/admin/courses/peserta/30816
                import re
                match = re.search(r'/courses/peserta/(\d+)', current_url)
                if match:
                    course_id = match.group(1)
                    print("ID Kelas ditemukan: {}".format(course_id))
                    send_telegram_message(telegram_id, "🆔 ID Kelas: {}".format(course_id))
                    
                    # Navigate to the attendance page
                    attendance_url = 'https://kolabjar-asnpintar.lan.go.id/admin/courses/{}/absensi-peserta'.format(course_id)
                    print("Mengakses halaman absensi: {}".format(attendance_url))
                    driver.get(attendance_url)
                    time.sleep(3)
                    
                    if mode == "pagi":
                        # Click the morning attendance button (absen pagi)
                        # Check if already checked-in (button disabled with text)
                        already_absen = False
                        try:
                            disabled_msg_elems = driver.find_elements(
                                By.XPATH,
                                '//a[contains(@class,"btn") and contains(@class,"disabled") and '\
                                'contains(normalize-space(.), "Anda sudah") and contains(normalize-space(.), "absensi pagi")]'
                            )
                            if disabled_msg_elems:
                                already_absen = True
                                print("Deteksi: Sudah melakukan absensi pagi (tombol disabled). Melewati klik.")
                                send_telegram_message(telegram_id, "ℹ️ Deteksi: Anda sudah melakukan absensi pagi.")
                        except Exception:
                            pass

                        if not already_absen:
                            print("Mencari tombol absen pagi...")
                            try:
                                # Try different possible selectors for the morning attendance button
                                attendance_button = None
                                
                                # Selector 1: Button with text "Absen Pagi"
                                try:
                                    attendance_button = driver.find_element(By.XPATH, '//a[contains(text(), "Absen Pagi") or contains(text(), "absen pagi")]')
                                except:
                                    pass
                                
                                # Selector 2: Button with href containing "pagi"
                                if not attendance_button:
                                    try:
                                        attendance_button = driver.find_element(By.XPATH, '//a[contains(@href, "pagi")]')
                                    except:
                                        pass
                                
                                # Selector 3: Any button in a list with "pagi" text
                                if not attendance_button:
                                    try:
                                        attendance_button = driver.find_element(By.XPATH, '//a[contains(normalize-space(.), "Pagi") or contains(normalize-space(.), "pagi")]')
                                    except:
                                        pass
                                
                                if attendance_button:
                                    print("Tombol absen pagi ditemukan, mengklik...")
                                    if click_element_safely(driver, attendance_button):
                                        time.sleep(3)
                                        send_telegram_message(telegram_id, "✅ Absen pagi berhasil dicatat!")
                                        absen_berhasil = True
                                    else:
                                        send_telegram_message(telegram_id, "❌ Gagal mengklik tombol absen pagi.")
                                else:
                                    print("Tombol absen pagi tidak ditemukan")
                                    send_telegram_message(telegram_id, "⚠️ Tombol absen pagi tidak ditemukan di halaman.")
                            except Exception as e:
                                error_msg = "❌ Gagal mengklik tombol absen pagi: {}".format(str(e))
                                print(error_msg)
                                send_telegram_message(telegram_id, error_msg)
                    
                    elif mode == "sore":
                        # Click the afternoon attendance button (absen sore)
                        # Check if already checked-out (button disabled with text)
                        already_absen = False
                        try:
                            disabled_msg_elems = driver.find_elements(
                                By.XPATH,
                                '//a[contains(@class,"btn") and contains(@class,"disabled") and '\
                                'contains(normalize-space(.), "Anda sudah") and contains(normalize-space(.), "absensi sore")]'
                            )
                            if disabled_msg_elems:
                                already_absen = True
                                print("Deteksi: Sudah melakukan absensi sore (tombol disabled). Melewati klik.")
                                send_telegram_message(telegram_id, "ℹ️ Deteksi: Anda sudah melakukan absensi sore.")
                        except Exception:
                            pass

                        if not already_absen:
                            print("Mencari tombol absen sore...")
                            try:
                                # Try different possible selectors for the afternoon attendance button
                                attendance_button = None
                                
                                # Selector 1: Button with text "Absen Sore"
                                try:
                                    attendance_button = driver.find_element(By.XPATH, '//a[contains(text(), "Absen Sore") or contains(text(), "absen sore")]')
                                except:
                                    pass
                                
                                # Selector 2: Button with href containing "sore"
                                if not attendance_button:
                                    try:
                                        attendance_button = driver.find_element(By.XPATH, '//a[contains(@href, "sore")]')
                                    except:
                                        pass
                                
                                # Selector 3: Any button in a list with "sore" text
                                if not attendance_button:
                                    try:
                                        attendance_button = driver.find_element(By.XPATH, '//a[contains(normalize-space(.), "Sore") or contains(normalize-space(.), "sore")]')
                                    except:
                                        pass
                                
                                if attendance_button:
                                    print("Tombol absen sore ditemukan, mengklik...")
                                    if click_element_safely(driver, attendance_button):
                                        time.sleep(3)
                                        send_telegram_message(telegram_id, "✅ Absen sore berhasil dicatat!")
                                        absen_berhasil = True
                                    else:
                                        send_telegram_message(telegram_id, "❌ Gagal mengklik tombol absen sore.")
                                else:
                                    print("Tombol absen sore tidak ditemukan")
                                    send_telegram_message(telegram_id, "⚠️ Tombol absen sore tidak ditemukan di halaman.")
                            except Exception as e:
                                error_msg = "❌ Gagal mengklik tombol absen sore: {}".format(str(e))
                                print(error_msg)
                                send_telegram_message(telegram_id, error_msg)
                    
                    # Only take and send screenshot if attendance was successful
                    if absen_berhasil:
                        # After absen, capture the specific section or table and send
                        sent_image_path = None
                        if mode == "pagi":
                            section_try_path = '/tmp/attendance_morning_section_{}.png'.format(telegram_id)
                            table_try_path = '/tmp/attendance_morning_table_{}.png'.format(telegram_id)
                        else:  # sore
                            section_try_path = '/tmp/attendance_afternoon_section_{}.png'.format(telegram_id)
                            table_try_path = '/tmp/attendance_afternoon_table_{}.png'.format(telegram_id)

                        # Try to scroll the date section to bottom before capture
                        if scroll_to_date_header(driver, DATE_HEADER_TEXT):
                            print("Scrolled to date header and to bottom: {}".format(DATE_HEADER_TEXT))
                            time.sleep(1)

                        if screenshot_between_comments(
                            driver,
                            'DAFTAR ABSENSI',
                            'END DETAIL PELATIHAN',
                            section_try_path,
                        ):
                            sent_image_path = section_try_path
                            print("Section screenshot saved to {}".format(sent_image_path))
                        else:
                            table_selector = 'table.table.table-bordered.table-striped'
                            if screenshot_first_element_by_css(driver, table_selector, table_try_path):
                                sent_image_path = table_try_path
                                print("Table screenshot saved to {}".format(sent_image_path))
                            else:
                                # Final fallback to full page if both fail
                                if mode == "pagi":
                                    fallback_path = '/tmp/attendance_morning_full_{}.png'.format(telegram_id)
                                else:  # sore
                                    fallback_path = '/tmp/attendance_afternoon_full_{}.png'.format(telegram_id)
                                driver.save_screenshot(fallback_path)
                                sent_image_path = fallback_path
                                print("Fallback full screenshot saved to {}".format(sent_image_path))
                        
                        # Send the chosen screenshot via Telegram
                        if send_telegram_photo(telegram_id, sent_image_path):
                            print("Attendance screenshot sent via Telegram successfully to {}!".format(telegram_id))
                            send_telegram_message(telegram_id, "📸 Screenshot absen {} telah dikirim.".format(mode))
                        else:
                            print("Failed to send attendance screenshot via Telegram to {}.".format(telegram_id))
                            send_telegram_message(telegram_id, "⚠️ Gagal mengirim screenshot absen {}.".format(mode))
                    elif not already_absen:
                        # If attendance failed and it wasn't because they were already checked in
                        send_telegram_message(telegram_id, "⚠️ Tidak mengirim screenshot karena absen tidak berhasil.")
                        
                else:
                    error_msg = "❌ Gagal mengekstrak ID kelas dari URL"
                    print(error_msg)
                    send_telegram_message(telegram_id, error_msg)
                
            except Exception as e:
                error_msg = "❌ Gagal menemukan atau mengklik tombol Detail: {}".format(str(e))
                print(error_msg)
                send_telegram_message(telegram_id, error_msg)
                
        except Exception as login_error:
            error_msg = "❌ Login gagal: {}".format(str(login_error))
            print(error_msg)
            send_telegram_message(telegram_id, error_msg)
            
    except Exception as e:
        error_msg = "❌ Terjadi kesalahan saat absen {}: {}".format(mode, str(e))
        print(error_msg)
        send_telegram_message(telegram_id, error_msg)
        import traceback
        traceback.print_exc()
        
    finally:
        # Wait for a few seconds to let you check the browser
        time.sleep(5)  # Wait for 5 seconds
        
        # Close the browser
        if driver:
            driver.quit()
            print("Browser ditutup.")
            
        # Send completion message
        send_telegram_message(telegram_id, "🏁 Proses absen {} selesai.".format(mode))

def absen_multi_user(mode):
    """Perform attendance (morning or afternoon) for all registered users"""
    # Get all users from database
    users = get_all_users()
    
    if not users:
        print("Tidak ada pengguna yang terdaftar.")
        return
    
    print("Menjalankan absen {} untuk {} pengguna...".format(mode, len(users)))
    
    for user in users:
        telegram_id, username, password = user
        # if telegram_id == '413217834':
        print("Menjalankan absen {} untuk pengguna {} (ID: {})".format(mode, username, telegram_id))
        absen_user(telegram_id, username, password, mode)
        print("Selesai absen {} untuk pengguna {} (ID: {})".format(mode, username, telegram_id))
        # send_telegram_message('413217834', "{} DONE".format(telegram_id))
        # Add a delay between users to avoid overwhelming the server
        time.sleep(5)

def main():
    """Main function to run the script"""
    if len(sys.argv) != 2:
        print("Penggunaan: python absen_otomatis.py [pagi|sore]")
        print("Contoh: python absen_otomatis.py pagi")
        return
    
    mode = sys.argv[1].lower()
    
    if mode not in ["pagi", "sore"]:
        print("Mode tidak dikenali. Gunakan 'pagi' atau 'sore'.")
        return
    
    absen_multi_user(mode)

if __name__ == "__main__":
    main()