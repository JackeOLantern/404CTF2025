
import re

input_file = "svc_x_events.txt"

event_blocks = []
current_block = []
with open(input_file, "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("TIMESTAMP: "):
            if current_block:
                event_blocks.append(current_block)
                current_block = []
        current_block.append(line.strip())
    if current_block:
        event_blocks.append(current_block)

print("✅ Analyse des événements contenant 'svc-x':\n")
for block in event_blocks:
    joined = " ".join(block)
    ts = next((line for line in block if line.startswith("TIMESTAMP: ")), "TIMESTAMP: ???")
    eventid = re.search(r"<EventID.*?>(\d+)</EventID>", joined)
    cmd = re.search(r"<Data Name=\"CommandLine\">(.*?)</Data>", joined)
    exe = re.search(r"<Data Name=\"NewProcessName\">(.*?)</Data>", joined)
    ip = re.search(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", joined)

    print(ts)
    if eventid:
        print(f"  → EventID: {eventid.group(1)}")
    if exe:
        print(f"  → Executable: {exe.group(1)}")
    if cmd:
        print(f"  → CommandLine: {cmd.group(1)}")
    if ip:
        print(f"  → IP found: {ip.group(0)}")
    print("")
