#!/usr/bin/env python3
import argparse, os, sys, tempfile, subprocess
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft, find_peaks

def to_wav_if_needed(path):
    if path.lower().endswith(".wav"):
        return path, None
    tmp = tempfile.NamedTemporaryFile(prefix="bird_", suffix=".wav", delete=False)
    tmp.close()
    cmd = ["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", tmp.name]
    subprocess.run(cmd, check=True)
    return tmp.name, tmp.name

def robust_band_detect(x, sr, fmin=1500, fmax=10000, nperseg=4096):
    if x.ndim > 1: x = x.mean(axis=1)
    x = x.astype(np.float32)

    noverlap = nperseg // 2
    f, t, Z = stft(x, fs=sr, window="hann", nperseg=nperseg, noverlap=noverlap, padded=True, boundary="zeros")
    mag2 = (np.abs(Z) ** 2)
    band = (f >= fmin) & (f <= fmax)
    f_band = f[band]
    E = np.percentile(mag2[band], 75, axis=1)
    E = E / (E.max() + 1e-12)

    peaks, props = find_peaks(E, prominence=0.15, distance=max(3, int(0.002 * f_band.size)))
    if len(peaks) == 0:
        idx = int(np.argmax(E))
    else:
        idx = peaks[np.argmax(props["prominences"])]
    f0 = float(f_band[idx])

    half = 0.5 * E.max()
    i_low = idx
    while i_low > 0 and E[i_low] > half: i_low -= 1
    i_high = idx
    while i_high < len(E) - 1 and E[i_high] > half: i_high += 1

    low = float(f_band[max(i_low, 0)])
    high = float(f_band[min(i_high, len(f_band)-1)])

    # largeur min/max
    min_bw, max_bw = 2000.0, 6000.0
    bw = high - low
    if bw < min_bw:
        d = (min_bw - bw) / 2
        low -= d; high += d
    elif bw > max_bw:
        c = 0.5*(low + high)
        low, high = c - max_bw/2, c + max_bw/2

    low = max(fmin, low); high = min(fmax, high)
    if high <= low: low, high = 2500.0, 8500.0
    return f0, low, high

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--fmin", type=float, default=1500.0)
    ap.add_argument("--fmax", type=float, default=10000.0)
    ap.add_argument("--nperseg", type=int, default=4096)
    args = ap.parse_args()

    wav_path, tmp = to_wav_if_needed(args.input)
    try:
        sr, data = wavfile.read(wav_path)  # returns (sr, array)
        # normaliser si int
        if np.issubdtype(data.dtype, np.integer):
            info = np.iinfo(data.dtype)
            data = data.astype(np.float32) / max(1, info.max)
        else:
            data = data.astype(np.float32)
    finally:
        if tmp:
            try: os.unlink(tmp)
            except: pass

    f0, low, high = robust_band_detect(data, sr, args.fmin, args.fmax, args.nperseg)

    print("\n=== Bande oiseaux détectée === - detect_bird_band_no_sf.py:82")
    print(f"Pic ~ {f0:.0f} Hz - detect_bird_band_no_sf.py:83")
    print(f"Bande suggérée : {low:.0f}{high:.0f} Hz\n - detect_bird_band_no_sf.py:84")

    base = os.path.splitext(os.path.basename(args.input))[0]
    out_bal = f"{base}__birds_auto.wav"
    out_str = f"{base}__birds_auto_strict.wav"

    # gate : range linéaire (0.01 ≈ -40 dB ; 0.0056 ≈ -45 dB)
    cmd_bal = (f'ffmpeg -y -i "{args.input}" -ac 1 '
               f'-filter:a "highpass=f={int(low)},lowpass=f={int(high)},'
               f'agate=threshold=0.025:ratio=12:attack=4:release=120:range=0.01,'
               f'dynaudnorm" "{out_bal}"')
    low_s = max(args.fmin, f0 - 1200); high_s = min(args.fmax, f0 + 1800)
    cmd_str = (f'ffmpeg -y -i "{args.input}" -ac 1 '
               f'-filter:a "highpass=f={int(low_s)},lowpass=f={int(high_s)},'
               f'agate=threshold=0.02:ratio=18:attack=3:release=90:range=0.0056,'
               f'dynaudnorm" "{out_str}"')

    print(">>> ffmpeg (équilibré): - detect_bird_band_no_sf.py:101")
    print(cmd_bal)
    print("\n>>> ffmpeg (stricte): - detect_bird_band_no_sf.py:103")
    print(cmd_str)

if __name__ == "__main__":
    main()
