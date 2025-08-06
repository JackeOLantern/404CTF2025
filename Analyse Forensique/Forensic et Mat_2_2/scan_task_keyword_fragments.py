
from Evtx.Evtx import Evtx
import xml.etree.ElementTree as ET
import argparse

KEYWORDS = ["WinUpdate", "Check"]

def scan_keywords(evtx_path, output_file="task_keyword_matches.txt"):
    matches = []

    with Evtx(evtx_path) as log:
        for record in log.records():
            try:
                timestamp = int(record.timestamp().timestamp())
                xml = record.xml()
                if any(k.lower() in xml.lower() for k in KEYWORDS):
                    matches.append((timestamp, xml.strip()))
            except Exception:
                continue

    if matches:
        with open(output_file, "w", encoding="utf-8") as f:
            for ts, xml in matches:
                f.write(f"TIMESTAMP: {ts}\n")
                f.write(xml + "\n\n")
        print(f"✅ {len(matches)} événement(s) contenant 'WinUpdate' ou 'Check' enregistré(s) dans {output_file}")
    else:
        print("❌ Aucun événement ne contient les mots-clés spécifiés.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recherche tous les fragments liés à une tâche par mot-clé")
    parser.add_argument("evtx_file", help="Fichier .evtx")
    args = parser.parse_args()

    scan_keywords(args.evtx_file)
