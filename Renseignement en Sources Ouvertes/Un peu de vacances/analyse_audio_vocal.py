import os
import sys
import json
import os, sys

# Cherche une installation locale de whisper dans ~/whisper_local
whisper_local = os.path.expanduser('~/whisper_local')
if os.path.isdir(whisper_local) and whisper_local not in sys.path:
    sys.path.insert(0, whisper_local)


# Tenter d'importer les bibliothèques optionnelles. En cas d'échec, définir des stubs.
try:
    import whisper  # type: ignore[assignment]
except ImportError:
    whisper = None  # type: ignore[assignment]

try:
    from pydub import AudioSegment  # type: ignore[assignment]
except ImportError:
    AudioSegment = None  # type: ignore[assignment]

try:
    from mutagen import File as MutagenFile  # type: ignore[assignment]
    from mutagen.id3 import ID3  # type: ignore[assignment]
except ImportError:
    MutagenFile = None  # type: ignore[assignment]
    ID3 = None  # type: ignore[assignment]

def convert_to_wav(input_file, output_file="converted.wav"):
    """
    Convertit un fichier MP3 en WAV en utilisant pydub si disponible.
    Si pydub est indisponible, laisse le fichier tel quel.

    :param input_file: Chemin du fichier d'entrée.
    :param output_file: Nom du fichier WAV de sortie.
    :return: Chemin du fichier à utiliser pour la suite.
    """
    # Normaliser l'extension en minuscules pour la comparaison
    if input_file.lower().endswith(".mp3"):
        if AudioSegment is None:
            # Impossible de convertir sans pydub, utiliser le fichier d'origine.
            print("[!] pydub indisponible : impossible de convertir MP3 vers WAV. - analyse_audio_vocal.py:43")
            return input_file
        # Utiliser from_file pour prendre en charge différents formats
        audio = AudioSegment.from_file(input_file)
        audio.export(output_file, format="wav")
        return output_file
    # Le fichier est déjà au format WAV (ou autre format pris en charge)
    return input_file

def extract_metadata(file_path):
    """
    Extrait les métadonnées d'un fichier audio si la bibliothèque mutagen est disponible.
    Retourne un dictionnaire vide en cas d'indisponibilité ou d'erreur.

    :param file_path: Chemin du fichier audio.
    :return: Dictionnaire contenant les métadonnées.
    """
    meta: dict[str, object] = {}
    if MutagenFile is None:
        # mutagen n'est pas installé, aucune métadonnée récupérable
        print("[!] Module 'mutagen' introuvable : pas de métadonnées disponibles. - analyse_audio_vocal.py:63")
        return meta
    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return meta
        # Extraire les informations génériques (durée, bitrate, etc.)
        if hasattr(audio, "info") and hasattr(audio.info, "__dict__"):
            meta.update(audio.info.__dict__)
        # Extraire les tags ID3 si présents
        if ID3 is not None and isinstance(audio.tags, ID3):
            for tag in audio.tags.values():
                if hasattr(tag, "text"):
                    meta[getattr(tag, 'FrameID', getattr(tag, 'desc', 'unknown'))] = tag.text
                elif hasattr(tag, "desc"):
                    meta[tag.desc] = tag.text
    except Exception as e:
        meta["error"] = str(e)
    return meta

def transcribe_audio(file_path, model_size="base"):
    """
    Transcrit un fichier audio en texte à l'aide de Whisper si disponible.
    Retourne une chaîne vide si le module whisper n'est pas installé ou qu'une erreur survient.

    :param file_path: Chemin du fichier audio.
    :param model_size: Taille du modèle Whisper à utiliser.
    :return: Texte transcrit ou chaîne vide.
    """
    if whisper is None:
        print("[!] Module 'whisper' introuvable : transcription impossible. - analyse_audio_vocal.py:93")
        return ""
    try:
        model = whisper.load_model(model_size)
        result = model.transcribe(file_path, language="fr")
        return result.get("text", "")
    except Exception as e:
        print(f"[!] Erreur lors de la transcription : {e} - analyse_audio_vocal.py:100")
        return ""

def main(audio_file):
    print(f"🔍 Analyse de: {audio_file} - analyse_audio_vocal.py:104")
    
    # Étape 1: Conversion en WAV si besoin
    wav_file = convert_to_wav(audio_file)
    
    # Étape 2: Transcription vocale
    print("\n🗣️ Transcription du message vocal: - analyse_audio_vocal.py:110")
    text = transcribe_audio(wav_file)
    print(text)
    
    # Étape 3: Métadonnées
    print("\n📎 Métadonnées extraites: - analyse_audio_vocal.py:115")
    metadata = extract_metadata(audio_file)
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    
    # Étape 4: Indice de localisation possible ?
    print("\n🌍 Déduction possible de localisation: - analyse_audio_vocal.py:120")
    keywords = ["Guyane", "Kourou", "CSG", "tropical", "fusée", "Ariane"]
    for word in keywords:
        if word.lower() in text.lower():
            print(f"🛰️ Motclé détecté: '{word}' → lieu potentiellement associé: Centre Spatial Guyanais - analyse_audio_vocal.py:124")
            break
    else:
        print("❓ Aucun motclé directement lié à un lieu connu détecté. - analyse_audio_vocal.py:127")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python  <fichier_audio.mp3|.wav> - analyse_audio_vocal.py:131")
    else:
        main(sys.argv[1])
