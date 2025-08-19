#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, re, bisect
from typing import List, Tuple, Optional
import numpy as np

# ============ Réglages ============

UNSTUFF = False  # Décochée pour ce challenge (pas besoin de retirer le bit stuffing)

# ============ Utilitaires ============

def run_lengths(arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    if arr.size == 0:
        return np.array([], dtype=arr.dtype), np.array([], dtype=int)
    change = np.diff(arr)
    idx = np.where(change != 0)[0] + 1
    starts = np.r_[0, idx]
    ends   = np.r_[idx, arr.size]
    vals   = arr[starts]
    lens   = ends - starts
    return vals, lens

def mode_near(values: np.ndarray, lo: int = 5, hi: int = 60) -> int:
    filt = values[(values >= lo) & (values <= hi)]
    if filt.size == 0:
        return int(np.median(values)) if values.size else 20
    uniq, cnt = np.unique(filt, return_counts=True)
    return int(uniq[np.argmax(cnt)])

def bits_to_bytes_lsb_first(bits: np.ndarray) -> List[int]:
    n = (len(bits) // 8) * 8
    out = []
    for i in range(0, n, 8):
        b = 0
        for k in range(8):
            b |= (int(bits[i+k]) & 1) << k
        out.append(b)
    return out

def pid_name(pid: int) -> Optional[str]:
    low = pid & 0xF
    high = (pid >> 4) & 0xF
    if high != (~low & 0xF):
        return None
    table = {
        0x1: "OUT",   0x9: "IN",    0xD: "SETUP", 0x5: "SOF",
        0x3: "DATA0", 0xB: "DATA1", 0x7: "DATA2", 0xF: "MDATA",
        0x2: "ACK",   0xA: "NAK",   0xE: "STALL", 0x6: "NYET",
        0xC: "PRE/ERR",
    }
    return table.get(low, f"PID_{low:X}")

def is_printable_ascii(b: int) -> bool:
    return 32 <= b <= 126

# ============ Étapes USB ============

def estimate_bit_period(dp: np.ndarray, dn: np.ndarray) -> int:
    state = np.sign(dp - dn)
    state[state == 0] = 1
    _, lens = run_lengths(state)
    return mode_near(lens, lo=5, hi=60)

def detect_sync_runs(dp: np.ndarray, dn: np.ndarray, base: int, tol: int = 2) -> List[int]:
    """
    SYNC (énoncé) vu en 'runs' du signe(D+−D−) :
      7 runs ~ base, puis 1 run >= ~ 2*base.
    Retourne les indices échantillons du début de SYNC.
    """
    state = np.sign(dp - dn)
    state[state == 0] = 1
    _, lens = run_lengths(state)
    cum = np.concatenate([[0], np.cumsum(lens[:-1])])
    starts = []
    i = 0
    while i + 8 <= len(lens):
        w = lens[i:i+8]
        if all(abs(int(x) - base) <= tol for x in w[:7]) and w[7] >= (2*base - tol):
            starts.append(int(cum[i]))
            i += 8
        else:
            i += 1
    return starts

def se0_mask(dp: np.ndarray, dn: np.ndarray, thr: Optional[float] = None) -> np.ndarray:
    if thr is None:
        thr = float(np.percentile(np.r_[dp, dn], 5)) + 0.05
    return (dp < thr) & (dn < thr)

def next_se0_after(se0_runs: List[Tuple[int,int]], pos: int) -> int:
    starts = [s for s,_ in se0_runs]
    idx = bisect.bisect_right(starts, pos)
    return starts[idx] if idx < len(starts) else 10**12

def decode_bits_between(dp: np.ndarray, dn: np.ndarray, base: int,
                        start_sample: int, end_sample: int, phase: int) -> np.ndarray:
    """
    Échantillonne au centre des cellules (phase ∈ [0..base-1]) et décode NRZI :
      1 = pas de transition, 0 = transition.
    """
    state = np.sign(dp - dn)
    state[state == 0] = 1
    first_center = start_sample + phase + base // 2
    idx = np.arange(first_center, end_sample, base, dtype=int)
    if idx.size < 2:
        return np.array([], dtype=int)
    s = state[idx]
    prev, cur = s[:-1], s[1:]
    return (prev == cur).astype(int)

def remove_bit_stuffing(bits: np.ndarray) -> np.ndarray:
    """Retire le '0' inséré après 6 '1' consécutifs (option, désactivée ici)."""
    out = []
    ones = 0
    i = 0
    n = len(bits)
    while i < n:
        b = int(bits[i])
        out.append(b)
        if b == 1:
            ones += 1
            if ones == 6:
                if i + 1 < n and bits[i+1] == 0:
                    i += 1  # skip stuffed 0
                ones = 0
        else:
            ones = 0
        i += 1
    return np.array(out, dtype=int)

def extract_frames(dp: np.ndarray, dn: np.ndarray, base: int, phase: int) -> List[List[int]]:
    """
    Découpe en trames : SYNC détecté, fin = EOP (SE0) ou prochain SYNC.
    Décode NRZI, (optionnellement) retire le bit-stuffing, puis assemble en octets LSB-first.
    """
    sync_starts = detect_sync_runs(dp, dn, base, tol=2)

    se0 = se0_mask(dp, dn)
    se0_vals, se0_lens = run_lengths(se0.astype(int))
    se0_runs, cursor = [], 0
    for v, ln in zip(se0_vals, se0_lens):
        if v == 1:
            se0_runs.append((cursor, int(ln)))
        cursor += int(ln)

    frames = []
    for i, s in enumerate(sync_starts):
        start_data = s + 8*base  # saute le SYNC (8 bits)
        end = min(next_se0_after(se0_runs, start_data),
                  sync_starts[i+1] if i+1 < len(sync_starts) else dp.size)
        bits = decode_bits_between(dp, dn, base, start_data, end, phase)
        if UNSTUFF:
            bits = remove_bit_stuffing(bits)
        frames.append(bits_to_bytes_lsb_first(bits))
    return frames

def classify_frames(frames_bytes: List[List[int]]) -> List[Tuple[str, List[int]]]:
    out = []
    for fb in frames_bytes:
        if not fb:
            out.append(("EMPTY", fb))
            continue
        out.append((pid_name(fb[0]) or "BAD", fb))
    return out

def data_payload(frame_bytes: List[int]) -> List[int]:
    if not frame_bytes:
        return []
    name = pid_name(frame_bytes[0])
    if not (name and name.startswith("DATA")):
        return []
    data = frame_bytes[1:]
    return data[:-2] if len(data) >= 2 else data  # on enlève CRC16 si présent

# ============ Chemins & phase ============

def locate_raw_pair(argv: List[str]) -> Tuple[str, str]:
    if len(argv) >= 3 and not argv[1].startswith("--"):
        return argv[1], argv[2]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cwd = os.getcwd()
    for d in (cwd, script_dir, os.path.join(cwd,"USB2"), os.path.join(script_dir,"USB2")):
        dp = os.path.join(d, "USB2_D_plus.raw")
        dn = os.path.join(d, "USB2_D_neg.raw")
        if os.path.exists(dp) and os.path.exists(dn):
            return dp, dn
    print("[!] Fichiers introuvables. Exemple : - usb2_flag_recover.py:189")
    print(f"python3 {os.path.basename(__file__)} USB2/USB2_D_plus.raw USB2/USB2_D_neg.raw - usb2_flag_recover.py:190", file=sys.stderr)
    sys.exit(1)

def reconstruct_text_for_phase(dp, dn, base, phase) -> str:
    frames = extract_frames(dp, dn, base, phase)
    classes = classify_frames(frames)
    chars = []
    for name, fb in classes:
        if name and name.startswith("DATA"):
            pl = data_payload(fb)
            # Prend TOUS les octets ASCII imprimables
            for b in pl:
                if is_printable_ascii(b):
                    chars.append(chr(b))
    return ''.join(chars)

def choose_best_phase(dp: np.ndarray, dn: np.ndarray, base: int) -> Tuple[int, str]:
    best_phase = 0
    best_text  = ""
    best_key   = (-1, -1)  # (nb_flags, len_text)
    for phase in range(base):
        text = reconstruct_text_for_phase(dp, dn, base, phase)
        nb_flags = len(re.findall(r"404CTF\{[0-9a-f]{64}\}", text))
        key = (nb_flags, len(text))
        if key > best_key:
            best_key = key
            best_text = text
            best_phase = phase
        # commentaire court utile au debug
        prev = (text[:50] + "...") if len(text) > 50 else text
        print(f"[scan phase {phase:02d}] flags={nb_flags} len={len(text)} preview='{prev}' - usb2_flag_recover.py:220")
    return best_phase, best_text

# ============ Main ============

def main():
    dp_path, dn_path = locate_raw_pair(sys.argv)
    print(f"[1] Fichiers :\n    D+ = {dp_path}\n    D = {dn_path} - usb2_flag_recover.py:227")

    dp = np.fromfile(dp_path, dtype=np.float32)
    dn = np.fromfile(dn_path, dtype=np.float32)
    if dp.size != dn.size:
        print("[!] Longueurs différentes entre D+ et D. - usb2_flag_recover.py:232", file=sys.stderr)
        sys.exit(1)
    print(f"Échantillons : {dp.size} - usb2_flag_recover.py:234")

    base = estimate_bit_period(dp, dn)
    print(f"[2] Période de bit estimée ≈ {base} échantillons - usb2_flag_recover.py:237")

    phase, text = choose_best_phase(dp, dn, base)
    print(f"[3] Phase choisie : {phase} (0..{base1}) - usb2_flag_recover.py:240")

    # Si besoin, re-génère le texte pour la phase retenue
    if not text:
        text = reconstruct_text_for_phase(dp, dn, base, phase)

    print("[4] Texte reconstruit : - usb2_flag_recover.py:246")
    print("    " + text)

    m = re.search(r"(404CTF\{[0-9a-f]{64}\})", text)
    if m:
        flag = m.group(1)
        print("\n[5] FLAG TROUVÉ ✅ - usb2_flag_recover.py:252")
        print("    " + flag)
    else:
        flag = None
        print("\n[5] Aucun flag au format attendu trouvé. - usb2_flag_recover.py:256")

    out = "usb2_recovered_flag.txt"
    with open(out, "w", encoding="utf-8") as f:
        if text:
            f.write(text + "\n")
        if flag:
            f.write(flag + "\n")
    print(f"[6] Résultat écrit dans : {os.path.abspath(out)} - usb2_flag_recover.py:264")

if __name__ == "__main__":
    main()
