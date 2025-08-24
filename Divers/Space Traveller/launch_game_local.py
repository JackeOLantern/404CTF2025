#!/usr/bin/env python3
# launch_game_local.py — 100% local (PWD), robuste vs score=None
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import time, re, sys

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

options = Options()
options.add_argument("--start-maximized")
options.add_argument("--allow-file-access-from-files")
options.add_argument("--allow-file-access")
driver = webdriver.Chrome(options=options)
driver.get(GAME_URL)

# Attendre que window.game.score existe
WebDriverWait(driver, 10).until(lambda d: d.execute_script("\nreturn (function(){\n  try {\n    if (typeof window === 'undefined') return false;\n    if (!window.game) return false;\n    var s = window.game.score;\n    if (typeof s === 'undefined' || s === null) return false;\n    return true;\n  } catch(e){ return false; }\n})();\n"))

time.sleep(0.2)
body = driver.find_element(By.TAG_NAME, "body")

with LOG_FILE.open("w") as log:
    log.write("tick,action,score\n")

tick = 0
last_action = "-"

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
                print(f"FLAG: {flag}")
                break

        if tick % 12 == 0:
            action = "Z" if last_action != "Z" else "S"
            body.send_keys(Keys.UP if action == "Z" else Keys.DOWN)
            last_action = action
        else:
            action = "-"

        with LOG_FILE.open("a") as log:
            log.write(f"{tick},{action},{score}\n")

        time.sleep(0.1)
finally:
    driver.quit()
