
from Evtx.Evtx import Evtx
import xml.etree.ElementTree as ET
import argparse
import re

TASKNAME_REGEX = re.compile(r'<Data Name="TaskName">(.*?)</Data>', re.IGNORECASE)
USER_REGEX = re.compile(r'<Data Name="(SubjectUserName|TargetUserName)">(.*?)</Data>', re.IGNORECASE)

def extract_tasks(evtx_path, output_file="all_tasknames_detected.txt"):
    tasks = []

    with Evtx(evtx_path) as log:
        for record in log.records():
            try:
                xml = record.xml()
                if "<EventID>4698</EventID>" not in xml:
                    continue

                timestamp = int(record.timestamp().timestamp())
                task_match = TASKNAME_REGEX.search(xml)
                user_match = USER_REGEX.search(xml)

                task = task_match.group(1).strip() if task_match else "UNKNOWN"
                user = user_match.group(2).strip() if user_match else "UNKNOWN"

                tasks.append((timestamp, task, user))

            except Exception:
                continue

    with open(output_file, "w", encoding="utf-8") as f:
        for ts, task, user in sorted(tasks):
            f.write(f"TIMESTAMP: {ts} | USER: {user} | TASKNAME: {task}\n")

    print(f"✅ {len(tasks)} tâche(s) détectée(s) et enregistrée(s) dans {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extrait toutes les tâches planifiées avec timestamp et utilisateur")
    parser.add_argument("evtx_file", help="Fichier .evtx à analyser")
    args = parser.parse_args()
    extract_tasks(args.evtx_file)
