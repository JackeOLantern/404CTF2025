import Evtx.Evtx as evtx
import xml.etree.ElementTree as ET
import re
import sys

NS = {"ns": "http://schemas.microsoft.com/win/2004/08/events/event"}
FLAG_REGEX = re.compile(r"404CTF\{[^}]+\}", re.IGNORECASE)

def extract_flag_from_evtx(path, log_path="flag_detection_log.txt"):
    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write(f"[+] Analyse de {path}\n")
        with evtx.Evtx(path) as log:
            for record in log.records():
                try:
                    root = ET.fromstring(record.xml())

                    event_id = root.find(".//ns:EventID", NS)
                    timestamp = root.find(".//ns:TimeCreated", NS)
                    eventdata = root.find(".//ns:EventData", NS)

                    if eventdata is not None:
                        for data in eventdata:
                            value = data.text
                            if isinstance(value, str) and FLAG_REGEX.search(value):
                                flag = FLAG_REGEX.search(value).group()
                                log_file.write("✅ Flag détecté !\n")
                                log_file.write(f"Flag      : {flag}\n")
                                log_file.write(f"EventID   : {event_id.text if event_id is not None else 'N/A'}\n")
                                log_file.write(f"Timestamp : {timestamp.attrib.get('SystemTime') if timestamp is not None else 'N/A'}\n")
                                log_file.write(f"Champ     : {data.attrib.get('Name', 'Inconnu')}\n")
                                print("✅ Flag détecté. Détails dans", log_path)
                                exit(0)
                except Exception:
                    continue

        log_file.write("❌ Aucun flag détecté.\n")
        print("❌ Aucun flag détecté. Voir", log_path)
        exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage : python3 detect_flag_evtx_log.py <fichier.evtx>")
        exit(1)
    else:
        extract_flag_from_evtx(sys.argv[1])
