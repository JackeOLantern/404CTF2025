#!/usr/bin/env python3
import argparse, sys
import numpy as np
from scipy.signal import resample_poly, butter, lfilter

def quad_demod(x):
    # Quadrature (polar) discriminator: angle(x[n] * conj(x[n-1]))
    return np.angle(x[1:] * np.conj(x[:-1]))

def design_lpf(fs, cutoff=6000.0, order=5):
    b, a = butter(order, cutoff/(fs/2.0), btype='low')
    return b, a

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iq", required=True, help="fichier IQ complex64")
    ap.add_argument("--fs", type=float, default=4_915_200, help="Fs IQ (Hz)")
    ap.add_argument("--fshift", type=float, default=135_000, help="décalage freq à centrer (Hz)")
    ap.add_argument("--audio_fs", type=int, default=22050, help="Fs audio sortie (Hz)")
    ap.add_argument("--gain", type=float, default=1.0, help="gain audio")
    args = ap.parse_args()

    # 1) charge IQ (complex64)
    iq = np.fromfile(args.iq, dtype=np.complex64)

    # 2) recentre à -fshift (on ramène la porteuse à 0 Hz)
    n = np.arange(iq.size)
    iq_shift = iq * np.exp(-1j * 2*np.pi*args.fshift * n / args.fs)

    # 3) FM/FSK: quadrature demod -> audio
    audio_f = quad_demod(iq_shift)

    # 4) anti-repliement + décimation vers 22.05 kHz
    #    (multimon-ng attend du S16LE @ 22050 Hz pour -t raw)
    b, a = design_lpf(args.fs)  # coupe ~6 kHz
    audio_f = lfilter(b, a, audio_f)

    # Décime proprement: resample_poly(., up=22050, down=Fs)
    up = args.audio_fs
    down = int(args.fs)
    audio = resample_poly(audio_f, up, down)

    # 5) normalisation vers int16 little-endian
    audio /= (np.max(np.abs(audio)) + 1e-9)
    audio_i16 = np.int16(np.clip(audio * args.gain, -1, 1) * 32767)

    # 6) sortie binaire brute sur stdout (pour pipe → multimon-ng)
    sys.stdout.buffer.write(audio_i16.tobytes())

if __name__ == "__main__":
    main()
