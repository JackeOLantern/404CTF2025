
from Evtx.Evtx import Evtx
import re

evtx_path = "CTFCORP_Security.evtx"
keyword = "payload"
results = []

ip_regex = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")
port_regex = re.compile(r"\b(\d{4,5})\b")
user_regex = re.compile(r'<Data Name=\"(SubjectUserName|TargetUserName)\">(.*?)</Data>', re.IGNORECASE)
group_regex = re.compile(r'<Data Name=\"GroupName\">(.*?)</Data>', re.IGNORECASE)

with Evtx(evtx_path) as log:
    for record in log.records():
        try:
            xml = record.xml()
            if keyword.lower() not in xml.lower():
                continue

            timestamp = int(record.timestamp().timestamp())
            ip_match = ip_regex.search(xml)
            port_match = port_regex.search(xml)
            user_match = user_regex.search(xml)
            group_match = group_regex.search(xml)

            result = {
                "timestamp": timestamp,
                "has_payload": True,
                "ip": ip_match.group(0) if ip_match else None,
                "port": port_match.group(1) if port_match else None,
                "user": user_match.group(2) if user_match else None,
                "group": group_match.group(1) if group_match else None,
                "snippet": xml[:500]
            }

            results.append(result)
        except Exception:
            continue

output_file = "payload_association_summary.txt"
with open(output_file, "w", encoding="utf-8") as f:
    for r in results:
        f.write(f"TIMESTAMP: {r['timestamp']}\n")
        f.write(f"USER: {r['user']} | IP: {r['ip']} | PORT: {r['port']} | GROUP: {r['group']}\n")
        f.write(f"XML Snippet: {r['snippet']}\n\n")

print(f"✅ Résumé des événements contenant 'payload' sauvegardé dans {output_file}")
