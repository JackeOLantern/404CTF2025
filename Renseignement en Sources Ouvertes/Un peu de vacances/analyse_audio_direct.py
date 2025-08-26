import sys
import os
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Try to import optional dependencies; fallback gracefully if missing.
try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None
import shutil

# Ajouter chemin vers whisper_local/whisper
sys.path.insert(0, os.path.expanduser("~/whisper_local"))

try:
    import whisper
except ImportError:
    whisper = None

def convert_mp3_to_wav(mp3_path, wav_path):
    """
    Convertit un fichier MP3 en WAV si la bibliothèque pydub est disponible.
    Si pydub n'est pas installée, copie simplement le fichier source à la destination.

    :param mp3_path: Chemin du fichier MP3 d'entrée.
    :param wav_path: Chemin du fichier WAV de sortie.
    """
    if AudioSegment is None:
        # Fallback : copier simplement le fichier source vers la destination.
        # On ne fait pas de réelle conversion faute de dépendance.
        shutil.copy(mp3_path, wav_path)
        print(f"[!] pydub indisponible : copie brute {mp3_path} → {wav_path} - analyse_audio_direct.py:33")
    else:
        audio = AudioSegment.from_file(mp3_path)
        audio.export(wav_path, format="wav")
        print(f"[+] Conversion : {mp3_path} → {wav_path} - analyse_audio_direct.py:37")

def transcribe_audio(wav_path):
    """
    Transcrit un fichier audio en texte à l'aide du modèle Whisper.
    Si la bibliothèque Whisper n'est pas installée ou qu'une erreur survient,
    retourne une chaîne vide et affiche un message informatif.

    :param wav_path: Chemin du fichier WAV à transcrire.
    :return: Texte transcrit ou chaîne vide si indisponible.
    """
    if whisper is None:
        print("[!] Module 'whisper' introuvable : transcription impossible. - analyse_audio_direct.py:49")
        return ""
    print("[*] Chargement du modèle Whisper... - analyse_audio_direct.py:51")
    try:
        model = whisper.load_model("base")
    except Exception as e:
        print(f"[!] Erreur lors du chargement du modèle Whisper : {e} - analyse_audio_direct.py:55")
        return ""
    print("[*] Transcription... - analyse_audio_direct.py:57")
    try:
        result = model.transcribe(wav_path, language="fr")
        return result.get("text", "")
    except Exception as e:
        print(f"[!] Erreur lors de la transcription : {e} - analyse_audio_direct.py:62")
        return ""

if __name__ == "__main__":
    mp3_file = "message_vocal.mp3"
    wav_file = "converted.wav"

    if not os.path.exists(mp3_file):
        print("❌ Fichier message_vocal.mp3 manquant. - analyse_audio_direct.py:70")
        sys.exit(1)

    convert_mp3_to_wav(mp3_file, wav_file)
    texte = transcribe_audio(wav_file)

    print("\n🗣️ Transcription : - analyse_audio_direct.py:76")
    print(texte)
