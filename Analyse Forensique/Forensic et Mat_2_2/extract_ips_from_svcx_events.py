
import re

input_file = "svc_x_events.txt"
ip_regex = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")

with open(input_file, "r", encoding="utf-8") as f:
    content = f.read()

blocks = content.split("TIMESTAMP:")
ip_blocks = []

for block in blocks[1:]:
    lines = block.strip().splitlines()
    ts = lines[0].strip()
    joined = " ".join(lines)
    found_ips = ip_regex.findall(joined)
    unique_ips = sorted(set(found_ips))
    if unique_ips:
        ip_blocks.append((ts, unique_ips))

if ip_blocks:
    with open("svc_x_ips_detected.txt", "w", encoding="utf-8") as f:
        for ts, ips in ip_blocks:
            f.write(f"TIMESTAMP: {ts}\n")
            for ip in ips:
                f.write(f"  → IP Detected: {ip}\n")
            f.write("\n")
    print("✅ IPs extraites depuis les événements svc-x et sauvegardées dans svc_x_ips_detected.txt")
else:
    print("❌ Aucune IP détectée dans les événements svc-x.")
