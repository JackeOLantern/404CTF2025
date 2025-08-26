import sys
import os
from pydub import AudioSegment

# Ajouter chemin vers whisper_local/whisper
sys.path.insert(0, os.path.expanduser("~/whisper_local"))

import whisper

def convert_mp3_to_wav(mp3_path, wav_path):
    audio = AudioSegment.from_mp3(mp3_path)
    audio.export(wav_path, format="wav")
    print(f"[+] Conversion : {mp3_path} → {wav_path}")

def transcribe_audio(wav_path):
    print("[*] Chargement du modèle Whisper...")
    model = whisper.load_model("base")
    print("[*] Transcription...")
    result = model.transcribe(wav_path, language="fr")
    return result["text"]

if __name__ == "__main__":
    mp3_file = "message_vocal.mp3"
    wav_file = "converted.wav"

    if not os.path.exists(mp3_file):
        print("❌ Fichier message_vocal.mp3 manquant.")
        sys.exit(1)

    convert_mp3_to_wav(mp3_file, wav_file)
    texte = transcribe_audio(wav_file)

    print("\n🗣️ Transcription :")
    print(texte)
