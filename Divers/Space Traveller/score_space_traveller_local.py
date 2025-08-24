#!/usr/bin/env python3
# score_space_traveller_local.py — 100% local (PWD), robuste vs score=None
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import time, csv, re, sys

def resolve_game_url() -> str:
    p = Path.cwd() / "space-traveller-mock.html"
    if p.exists(): return p.as_uri()
    q = Path("/mnt/data/Space Traveller/space-traveller-mock.html")
    if q.exists(): return q.as_uri()
    r = Path("/mnt/data/space-traveller-mock.html")
    if r.exists(): return r.as_uri()
    sys.exit("ERREUR: 'space-traveller-mock.html' introuvable (PWD ou /mnt/data).")

GAME_URL = resolve_game_url()
FINISH_SCORE = 90

options = Options()
options.add_argument("--start-maximized")
options.add_argument("--allow-file-access-from-files")
options.add_argument("--allow-file-access")
driver = webdriver.Chrome(options=options)
driver.get(GAME_URL)

WebDriverWait(driver, 10).until(lambda d: d.execute_script("\nreturn (function(){\n  try {\n    if (typeof window === 'undefined') return false;\n    if (!window.game) return false;\n    var s = window.game.score;\n    if (typeof s === 'undefined' || s === null) return false;\n    return true;\n  } catch(e){ return false; }\n})();\n"))

log_path = Path.cwd() / "log.csv"
with log_path.open("w", newline="") as log:
    w = csv.writer(log); w.writerow(["tick","action","score"])

tick = 0
body = driver.find_element(By.TAG_NAME, "body")
last_action = "-"

try:
    with log_path.open("a", newline="") as log:
        w = csv.writer(log)
        while True:
            tick += 1
            js_score = driver.execute_script("\nreturn (function(){\n  try {\n    var g = window.game || {};\n    var s = g.score;\n    if (typeof s === 'number' && isFinite(s)) return Math.floor(s);\n    if (typeof s === 'string') {\n      var n = parseInt(s, 10);\n      if (isFinite(n)) return n;\n    }\n    return 0;\n  } catch(e){ return 0; }\n})();\n")
            try:
                score = int(js_score) if js_score is not None else 0
            except Exception:
                score = 0

            if score >= FINISH_SCORE:
                text = driver.execute_script("return document.body.innerText || '';")
                m = re.search(r"404CTF\{[^}]+\}", text)
                if m:
                    flag = m.group(0)
                    print(f"FLAG: {flag}")
                    (Path.cwd() / "flag.txt").write_text(flag, encoding="utf-8")
                    break

            if tick % 10 == 0:
                action = "Z" if last_action != "Z" else "S"
                body.send_keys(Keys.UP if action == "Z" else Keys.DOWN)
                last_action = action
            else:
                action = "-"

            w.writerow([tick, action, score])
            time.sleep(0.1)
finally:
    driver.quit()
