import xml.etree.ElementTree as ET
from Evtx.Evtx import Evtx
import argparse

def extract_events(evtx_path):
    with Evtx(evtx_path) as log:
        for record in log.records():
            try:
                xml = record.xml()
                yield record.record_id(), record.timestamp(), xml
            except Exception as e:
                continue

def find_suspicious_events(evtx_path):
    for record_id, timestamp, xml in extract_events(evtx_path):
        try:
            root = ET.fromstring(xml)
            event_id = root.findtext(".//EventID")
            data = " ".join((elem.text or "") for elem in root.iter() if elem.text)

            if any(keyword in data.lower() for keyword in ["flag", "404ctf", "powershell", "logon", "administrator", "secre", "cmd", "whoami"]):
                print("=" * 80)
                print(f"Record ID: {record_id} | Timestamp: {timestamp}")
                print(f"Event ID: {event_id}")
                print(data)
                print("=" * 80)
        except Exception:
            continue

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract and search suspicious events in .evtx log")
    parser.add_argument("evtx_file", help="Path to the .evtx file")
    args = parser.parse_args()
    
    print(f"Analyzing {args.evtx_file}...\n")
    find_suspicious_events(args.evtx_file)
