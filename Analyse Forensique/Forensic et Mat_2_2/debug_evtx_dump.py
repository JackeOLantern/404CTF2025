import Evtx.Evtx as evtx
import xml.etree.ElementTree as ET
from datetime import datetime

with evtx.Evtx("CTFCORP_Security.evtx") as log:
    for record in log.records():
        xml = record.xml()
        try:
            root = ET.fromstring(xml)
            time_attr = root.find(".//TimeCreated").attrib.get("SystemTime")
            timestamp = int(datetime.fromisoformat(time_attr.replace("Z", "+00:00")).timestamp())

            for data in root.findall(".//Data"):
                name = data.attrib.get("Name")
                value = data.text
                if name and value:
                    print(f"{name}: {value}")
            print("Timestamp UNIX:", timestamp)
            print("="*60)
        except Exception as e:
            continue
