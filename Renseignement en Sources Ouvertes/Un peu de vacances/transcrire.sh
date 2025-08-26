#!/bin/bash
set -e

# Dépendances : ffmpeg + whisper_local cloné dans ~/whisper_local

echo "🎧 Conversion MP3 → WAV avec ffmpeg..."
ffmpeg -y -i message_vocal.mp3 converted.wav

echo "🤖 Transcription avec Whisper (modèle base)..."
python3 <<EOF
import sys, os
sys.path.insert(0, os.path.expanduser("~/whisper_local"))
import whisper

model = whisper.load_model("base")
result = model.transcribe("converted.wav", language="fr")

print("\n🗣️ Transcription détectée :\n")
print(result["text"])
EOF
