
import re

input_file = "task_keyword_matches.txt"
port_regex = re.compile(r"\b(\d{4,5})\b")

with open(input_file, "r", encoding="utf-8") as f:
    content = f.read()

blocks = content.split("TIMESTAMP:")
port_matches = []

for block in blocks[1:]:
    lines = block.strip().splitlines()
    ts = lines[0].strip()
    joined = " ".join(lines)
    found_ports = port_regex.findall(joined)
    unique_ports = sorted(set(found_ports))
    if unique_ports:
        port_matches.append((ts, unique_ports))

if port_matches:
    with open("task_ports_detected.txt", "w", encoding="utf-8") as f:
        for ts, ports in port_matches:
            f.write(f"TIMESTAMP: {ts}\n")
            for port in ports:
                f.write(f"  → Port found: {port}\n")
            f.write("\n")
    print("✅ Ports extraits et sauvegardés dans task_ports_detected.txt")
else:
    print("❌ Aucun port trouvé dans les événements liés à 'WinUpdate' ou 'Check'")
