#!/bin/bash

set -e

# 1. Création d'un environnement virtuel
echo "[*] Création d’un environnement virtuel ./venv"
python3 -m venv venv
source venv/bin/activate

# 2. Mise à jour pip
echo "[*] Mise à jour de pip"
pip install --upgrade pip

# 3. Installation des dépendances Python
echo "[*] Installation de whisper, pydub, mutagen"
pip install openai-whisper pydub mutagen

# 4. Installation de ffmpeg si besoin
echo "[*] Installation de ffmpeg (via apt)"
sudo apt update
sudo apt install -y ffmpeg

# 5. Vérification de whisper
echo "[*] Version de Whisper installée :"
python -c "import whisper; print(whisper.__version__)"

# 6. Lancer l'analyse
echo "[*] Analyse du fichier : message_vocal.mp3"
python analyse_audio_vocal.py message_vocal.mp3
