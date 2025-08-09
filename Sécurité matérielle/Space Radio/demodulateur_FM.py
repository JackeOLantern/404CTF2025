import numpy as np
import sounddevice as sd
import matplotlib.pyplot as plt
from scipy.signal import decimate
from matplotlib.animation import FuncAnimation
# === Paramètres ===
filename = "chall.iq"
fs = 48000
decim = 4
block_size = 4096
sample_rate = fs // decim
# === Chargement des données IQ ===
iq = np.fromfile(filename, dtype=np.complex64)

# === Préparation de l'affichage ===
fig, ax = plt.subplots()
spec_data = np.zeros((100, 256))
im = ax.imshow(spec_data, aspect='auto', origin='lower', extent=[0, sample_rate//2, 0, 100])
ax.set_title("Spectrogramme en direct")
ax.set_xlabel("Fréquence (Hz)")
ax.set_ylabel("Temps")
# === Générateur de blocs audio démodulés ===
def audio_generator():
    for i in range(0, len(iq) - block_size, block_size):
        block = iq[i:i+block_size]
        phase = np.unwrap(np.angle(block))
        demod = np.diff(phase)
        demod /= np.max(np.abs(demod)) + 1e-6
        audio = decimate(demod, decim)
        yield audio.astype(np.float32)
# === Animation du spectrogramme ===
def update(frame):
    audio = next(audio_blocks, np.zeros(block_size // decim))
    fft = np.abs(np.fft.rfft(audio, 512))[:256]
    fft = 20 * np.log10(fft + 1e-2)
    spec_data[:-1] = spec_data[1:]
    spec_data[-1] = fft
    im.set_data(spec_data)
    return [im]
# === Audio output ===
audio_blocks = audio_generator()
sd.play(np.concatenate(list(audio_blocks)), samplerate=sample_rate)
# === Lancer l'affichage ===
ani = FuncAnimation(fig, update, interval=50, blit=True)
plt.show()
