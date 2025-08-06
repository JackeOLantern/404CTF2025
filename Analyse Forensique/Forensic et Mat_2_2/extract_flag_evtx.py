import Evtx.Evtx as evtx
import xml.etree.ElementTree as ET
from datetime import datetime
import re

with evtx.Evtx("CTFCORP_Security.evtx") as log:
    for record in log.records():
        xml = record.xml()
        if "TaskName" in xml and "EventTimestamp" in xml:
            try:
                root = ET.fromstring(xml)
                data = {d.attrib.get("Name"): d.text for d in root.findall(".//Data")}
                ip = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', xml)
                port = re.search(r'\b\d{2,5}\b', xml)
                user = data.get("TargetUserName") or data.get("SubjectUserName")
                taskname = data.get("TaskName", "").split("\\")[-1]
                group = next((g for g in ["Administrators", "Users", "Guests", "Remote Desktop Users"] if g in xml), None)

                time_attr = root.find(".//TimeCreated").attrib.get("SystemTime")
                timestamp = int(datetime.fromisoformat(time_attr.replace("Z", "+00:00")).timestamp())

                if all([ip, port, user, taskname, group, timestamp]):
                    print("[+] Détails extraits :")
                    print("    ip               =", ip.group())
                    print("    port             =", port.group())
                    print("    user             =", user)
                    print("    taskname         =", taskname)
                    print("    event timestamp  =", timestamp)
                    print("    group            =", group)
                    print(f"\nFlag potentiel : 404CTF{{{ip.group()}-{port.group()}-{user}-{taskname}-{timestamp}-{group}}}\n")
            except Exception as e:
                continue
