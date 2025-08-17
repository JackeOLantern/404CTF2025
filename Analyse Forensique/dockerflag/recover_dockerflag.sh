#!/bin/bash

set -e

# Répertoire de travail
WORKDIR="docker_analysis"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

echo "[*] Étape 1 : Extraction de l'image Docker"
tar -xf ../dockerflag.tar

echo "[*] Étape 2 : Décompression de toutes les couches .tar.gz"
mkdir -p layers
jq -r '.[0].Layers[]' manifest.json | while read layer; do
  echo "[+] Extraction de $layer"
  tar -xf "$layer" -C layers/
done

echo "[*] Étape 3 : Recherche d’un répertoire .git"
FOUND_GIT=$(find layers/ -type d -name ".git" | head -n 1)
if [[ -z "$FOUND_GIT" ]]; then
  echo "[-] Aucun .git trouvé."
  exit 1
else
  echo "[+] .git trouvé : $FOUND_GIT"
fi

echo "[*] Étape 4 : Reconstruction du dépôt Git"
mkdir -p repo
cp -r "$FOUND_GIT" repo/.git
cd repo
git init > /dev/null
git checkout main || git checkout master || true

echo "[*] Étape 5 : Recherche de commits contenant un fichier .env"
ENV_FILE=$(git ls-tree -r HEAD | grep "\.env" | awk '{print $4}' | head -n 1)
if [[ -z "$ENV_FILE" ]]; then
  echo "[-] Aucun fichier .env trouvé dans le dépôt."
  exit 1
fi

echo "[+] Fichier .env détecté : $ENV_FILE"
echo "[*] Extraction du flag depuis l’ancien commit :"
FLAG=$(git show HEAD:$ENV_FILE | grep -oE '404CTF\{[^\}]+\}')
echo "[+] ✅ FLAG TROUVÉ : $FLAG"
