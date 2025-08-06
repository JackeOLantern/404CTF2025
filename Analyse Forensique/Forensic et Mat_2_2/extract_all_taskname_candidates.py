
from Evtx.Evtx import Evtx
import re
import argparse

# Regex : cherche des noms de tâche sous forme \Nom, Nom_Tache, etc.
TASKNAME_REGEX = re.compile(r"(?:\\|/)?([A-Za-z0-9_\-]{6,})")

def extract_all_taskname_candidates(evtx_path, output_file="all_taskname_candidates.txt"):
    candidates = set()

    with Evtx(evtx_path) as log:
        for record in log.records():
            try:
                xml = record.xml()
                found = TASKNAME_REGEX.findall(xml)
                for name in found:
                    if any(kw in name.lower() for kw in ["task", "update", "check", "sched", "engine", "payload"]):
                        candidates.add(name)
            except Exception:
                continue

    if candidates:
        with open(output_file, "w", encoding="utf-8") as f:
            for name in sorted(candidates):
                f.write(name + "\n")
        print(f"✅ {len(candidates)} nom(s) de tâche candidat(s) extrait(s) dans {output_file}")
    else:
        print("❌ Aucun nom de tâche trouvé dans le journal.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extraction brute de tous les noms de tâche potentiels")
    parser.add_argument("evtx_file", help="Fichier .evtx")
    args = parser.parse_args()

    extract_all_taskname_candidates(args.evtx_file)
