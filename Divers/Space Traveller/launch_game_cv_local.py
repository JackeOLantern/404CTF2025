#!/usr/bin/env python3
# launch_game_cv_local.py — 100% local (PWD), robuste vs score=None, canvas OK
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import base64, cv2, numpy as np, time, re, sys

def resolve_game_url() -> str:
    p = Path.cwd() / "space-traveller-mock.html"
    if p.exists(): return p.as_uri()
    q = Path("/mnt/data/Space Traveller/space-traveller-mock.html")
    if q.exists(): return q.as_uri()
    r = Path("/mnt/data/space-traveller-mock.html")
    if r.exists(): return r.as_uri()
    sys.exit("ERREUR: 'space-traveller-mock.html' introuvable (PWD ou /mnt/data).")

GAME_URL = resolve_game_url()
SCORE_TARGET = 90
FLAG_FILE = Path.cwd() / "flag.txt"
LOG_FILE = Path.cwd() / "log.csv"
TICK_DURATION = 0.15

options = Options()
options.add_argument("--start-maximized")
options.add_argument("--allow-file-access-from-files")
options.add_argument("--allow-file-access")
driver = webdriver.Chrome(options=options)
driver.get(GAME_URL)

WebDriverWait(driver, 10).until(lambda d: d.execute_script("\nreturn (function(){\n  try {\n    if (typeof window === 'undefined') return false;\n    if (!window.game) return false;\n    var s = window.game.score;\n    if (typeof s === 'undefined' || s === null) return false;\n    return true;\n  } catch(e){ return false; }\n})();\n"))
time.sleep(0.2)
canvas = driver.find_element(By.TAG_NAME, "canvas")
body = driver.find_element(By.TAG_NAME, "body")

with LOG_FILE.open("w") as log:
    log.write("tick,action,score\n")

tick = 0
last_action = "-"

def get_canvas_image():
    data_url = driver.execute_script("return document.querySelector('canvas').toDataURL('image/png');")
    encoded = data_url.split(",", 1)[1]
    img_bytes = base64.b64decode(encoded)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def detect_obstacles(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    obstacles = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > 10 and h > 50:
            obstacles.append((x, y, w, h))
    return sorted(obstacles, key=lambda r: r[0])

def detect_spaceship_y(img):
    h, w = img.shape[:2]
    roi = img[:, 0:120]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, binarized = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    ys, xs = np.where(binarized > 0)
    return int(np.mean(ys)) if len(ys) else h // 2

try:
    while True:
        tick += 1
        js_score = driver.execute_script("\nreturn (function(){\n  try {\n    var g = window.game || {};\n    var s = g.score;\n    if (typeof s === 'number' && isFinite(s)) return Math.floor(s);\n    if (typeof s === 'string') {\n      var n = parseInt(s, 10);\n      if (isFinite(n)) return n;\n    }\n    return 0;\n  } catch(e){ return 0; }\n})();\n")
        try:
            score = int(js_score) if js_score is not None else 0
        except Exception:
            score = 0

        if score >= SCORE_TARGET:
            page_text = driver.execute_script("return document.body.innerText || '';")
            match = re.search(r"404CTF\{[^}]+\}", page_text)
            if match:
                flag = match.group(0)
                FLAG_FILE.write_text(flag, encoding="utf-8")
                print(f"FLAG: {flag} (score={score})")
                break

        # Capture & pilotage (optionnel sur mock, conservé pour fidélité)
        canvas_img = get_canvas_image()
        obstacles = detect_obstacles(canvas_img)
        ship_y = detect_spaceship_y(canvas_img)

        action = "-"
        if obstacles:
            x, y, w, h = obstacles[0]
            gap_up = y - 12
            gap_down = y + h + 12
            if abs(ship_y - gap_up) < abs(ship_y - gap_down):
                body.send_keys(Keys.UP); action = "Z"
            else:
                body.send_keys(Keys.DOWN); action = "S"

        with LOG_FILE.open("a") as log:
            log.write(f"{tick},{action},{score}\n")

        time.sleep(TICK_DURATION)
finally:
    driver.quit()
