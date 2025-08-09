# ifft_recover.py
# Usage:
#   python3 ifft_recover.py --iq chall.iq --out recovered.wav --rate 44100 --compare recovered_signal.wav
#
# Requiert: numpy (pip install numpy)

import argparse, hashlib, wave, contextlib
import numpy as np
from pathlib import Path

def write_wav_int16(path, pcm16, fs):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)        # int16
        w.setframerate(fs)
        w.writeframes(pcm16.tobytes())

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def first_diff(a: bytes, b: bytes) -> int | None:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    if len(a) != len(b):
        return n  # diverge at EOF
    return None  # identical

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--iq", required=True, help="fichier IQ Complex128 (DFT complète)")
    p.add_argument("--out", default="recovered.wav", help="sortie WAV int16 mono")
    p.add_argument("--rate", type=int, default=44100, help="fréquence d’échantillonnage du WAV")
    p.add_argument("--compare", help="WAV de référence à comparer octet-par-octet (optionnel)")
    args = p.parse_args()

    iq_path = Path(args.iq)
    out_path = Path(args.out)

    # 1) Charger X[k] (complex128) et appliquer l’iFFT -> x[n]
    X = np.fromfile(iq_path, dtype=np.complex128)
    x = np.fft.ifft(X)  # IDFT 1D inverse de fft() à la précision numérique près

    # 2) Réel + normalisation EXACTE (pour identité binaire avec notre référence)
    sig = np.real(x)
    mx = np.max(np.abs(sig)) or 1.0
    pcm16 = (sig / mx * 32767).astype(np.int16)

    # 3) Écrire le WAV PCM int16 mono
    write_wav_int16(out_path, pcm16, args.rate)

    # 4) Hash et (optionnel) comparaison binaire
    h_out = sha256_of(out_path)
    print(f"[OK] Écrit: {out_path}  SHA-256={h_out}")

    if args.compare:
        ref = Path(args.compare)
        h_ref = sha256_of(ref)
        print(f"[i] Référence: {ref}  SHA-256={h_ref}")
        same = (h_out == h_ref)
        if same:
            print("[OK] Identiques (SHA-256).")
        else:
            a = out_path.read_bytes()
            b = ref.read_bytes()
            pos = first_diff(a, b)
            print(f"[!] Différence détectée à l’octet {pos} (ou à la fin si None).")

if __name__ == "__main__":
    main()
