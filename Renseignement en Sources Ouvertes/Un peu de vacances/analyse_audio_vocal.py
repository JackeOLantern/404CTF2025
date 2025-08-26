import os
import sys
import whisper
from pydub import AudioSegment
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TIT2, TPE1, COMM, TXXX
import json

def convert_to_wav(input_file, output_file="converted.wav"):
    if input_file.endswith(".mp3"):
        audio = AudioSegment.from_mp3(input_file)
        audio.export(output_file, format="wav")
        return output_file
    return input_file  # already WAV

def extract_metadata(file_path):
    meta = {}
    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return meta
        meta.update(audio.info.__dict__)
        if isinstance(audio.tags, ID3):
            for tag in audio.tags.values():
                if hasattr(tag, "text"):
                    meta[tag.FrameID] = tag.text
                elif hasattr(tag, "desc"):
                    meta[tag.desc] = tag.text
    except Exception as e:
        meta['error'] = str(e)
    return meta

def transcribe_audio(file_path, model_size="base"):
    model = whisper.load_model(model_size)
    result = model.transcribe(file_path, language="fr")
    return result['text']

def main(audio_file):
    print(f"🔍 Analyse de: {audio_file}")
    
    # Étape 1: Conversion en WAV si besoin
    wav_file = convert_to_wav(audio_file)
    
    # Étape 2: Transcription vocale
    print("\n🗣️ Transcription du message vocal:")
    text = transcribe_audio(wav_file)
    print(text)
    
    # Étape 3: Métadonnées
    print("\n📎 Métadonnées extraites:")
    metadata = extract_metadata(audio_file)
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    
    # Étape 4: Indice de localisation possible ?
    print("\n🌍 Déduction possible de localisation:")
    keywords = ["Guyane", "Kourou", "CSG", "tropical", "fusée", "Ariane"]
    for word in keywords:
        if word.lower() in text.lower():
            print(f"🛰️ Mot-clé détecté: '{word}' → lieu potentiellement associé: Centre Spatial Guyanais")
            break
    else:
        print("❓ Aucun mot-clé directement lié à un lieu connu détecté.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyse_audio_vocal.py <fichier_audio.mp3|.wav>")
    else:
        main(sys.argv[1])
