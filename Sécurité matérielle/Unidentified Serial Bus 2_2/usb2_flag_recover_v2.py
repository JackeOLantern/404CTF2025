#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, re, bisect
from typing import List, Tuple, Optional
import numpy as np

# --- Réglages ---
UNSTUFF = False        # pas de bit stuffing pour ce challenge
SE0_THR = 0.15         # seuil simple pour détecter SE0 (deux lignes basses)

# --- Utilitaires ---
def run_lengths(arr: np.ndarray):
    if arr.size == 0:
        return np.array([], dtype=arr.dtype), np.array([], dtype=int)
    change = np.diff(arr)
    idx = np.where(change != 0)[0] + 1
    starts = np.r_[0, idx]
    ends   = np.r_[idx, arr.size]
    return arr[starts], ends - starts

def mode_near(values: np.ndarray, lo=5, hi=60) -> int:
    filt = values[(values >= lo) & (values <= hi)]
    if filt.size == 0:
        return int(np.median(values)) if values.size else 20
    uniq, cnt = np.unique(filt, return_counts=True)
    return int(uniq[np.argmax(cnt)])

def bits_to_bytes_lsb_first(bits: np.ndarray):
    n = (len(bits)//8)*8
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
    table = {0x1:"OUT",0x9:"IN",0xD:"SETUP",0x5:"SOF",
             0x3:"DATA0",0xB:"DATA1",0x7:"DATA2",0xF:"MDATA",
             0x2:"ACK",0xA:"NAK",0xE:"STALL",0x6:"NYET",0xC:"PRE/ERR"}
    return table.get(low, f"PID_{low:X}")

def is_printable_ascii(b: int) -> bool:
    return 32 <= b <= 126

# --- Étapes USB ---
def estimate_bit_period(dp: np.ndarray, dn: np.ndarray) -> int:
    state = np.sign(dp - dn)
    state[state == 0] = 1
    _, lens = run_lengths(state)
    return mode_near(lens, lo=5, hi=60)

def detect_sync_runs_from_state(state: np.ndarray, base: int, tol: int = 2) -> List[int]:
    # SYNC dans le domaine des runs: 7 runs ~base puis 1 run >= ~2*base
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

def se0_mask(dp: np.ndarray, dn: np.ndarray) -> np.ndarray:
    return (dp < SE0_THR) & (dn < SE0_THR)

def next_se0_after(se0_runs: List[Tuple[int,int]], pos: int) -> int:
    starts = [s for s,_ in se0_runs]
    idx = bisect.bisect_right(starts, pos)
    return starts[idx] if idx < len(starts) else 10**12

def decode_bits_between_state(state: np.ndarray, base: int, start: int, end: int, phase: int) -> np.ndarray:
    # NRZI: 1 = pas de transition, 0 = transition
    first_center = start + phase + base // 2
    idx = np.arange(first_center, end, base, dtype=int)
    if idx.size < 2:
        return np.array([], dtype=int)
    s = state[idx]
    prev, cur = s[:-1], s[1:]
    return (prev == cur).astype(int)

def remove_bit_stuffing(bits: np.ndarray) -> np.ndarray:
    out, ones, i, n = [], 0, 0, len(bits)
    while i < n:
        b = int(bits[i]); out.append(b)
        if b == 1:
            ones += 1
            if ones == 6:
                if i + 1 < n and bits[i+1] == 0:
                    i += 1
                ones = 0
        else:
            ones = 0
        i += 1
    return np.array(out, dtype=int)

def extract_frames_with_state(state: np.ndarray, dp: np.ndarray, dn: np.ndarray, base: int, phase: int):
    sync_starts = detect_sync_runs_from_state(state, base, tol=2)

    se0 = se0_mask(dp, dn)
    se0_vals, se0_lens = run_lengths(se0.astype(int))
    se0_runs, cur = [], 0
    for v, ln in zip(se0_vals, se0_lens):
        if v == 1: se0_runs.append((cur, int(ln)))
        cur += int(ln)

    frames = []
    for s in sync_starts:
        start_data = s + 8*base  # saute les 8 bits de SYNC
        end = next_se0_after(se0_runs, start_data)  # fin stricte à EOP
        if end <= start_data: 
            continue
        bits = decode_bits_between_state(state, base, start_data, end, phase)
        if UNSTUFF:
            bits = remove_bit_stuffing(bits)
        frames.append(bits_to_bytes_lsb_first(bits))
    return frames

def classify_frames(frames):
    out=[]
    for fb in frames:
        if not fb: out.append(("EMPTY", fb)); continue
        out.append((pid_name(fb[0]) or "BAD", fb))
    return out

def data_payload(frame_bytes: List[int]) -> List[int]:
    if not frame_bytes:
        return []
    name = pid_name(frame_bytes[0])
    if not (name and name.startswith("DATA")):
        return []
    data = frame_bytes[1:]
    return data[:-2] if len(data) >= 2 else data  # on coupe juste le CRC16

# --- Chemins & sélection ---
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
    print("[!] Fichiers introuvables. Exemple :  usb2_flag_recover.py:156 - usb2_flag_recover_v2.py:156")
    print(f"python3 {os.path.basename(__file__)} USB2/USB2_D_plus.raw USB2/USB2_D_neg.raw  usb2_flag_recover.py:157 - usb2_flag_recover_v2.py:157", file=sys.stderr)
    sys.exit(1)

def text_from_frames(classes) -> str:
    chars=[]
    for name, fb in classes:
        if name and name.startswith("DATA"):
            pl = data_payload(fb)
            for b in pl:
                if is_printable_ascii(b):
                    chars.append(chr(b))
    return ''.join(chars)

def score_text(txt: str) -> Tuple[int, int, int]:
    # maximise: flag complet > longueur hex après '404CTF{' > longueur totale
    m_full = re.search(r"404CTF\{([0-9a-f]{64})\}", txt)
    if m_full:
        return (1, 64, len(txt))
    m_partial = re.search(r"404CTF\{([0-9a-f]+)", txt)
    hexlen = len(m_partial.group(1)) if m_partial else 0
    return (0, hexlen, len(txt))

# --- Main ---
def main():
    dp_path, dn_path = locate_raw_pair(sys.argv)
    print(f"[1] Fichiers :\n    D+ = {dp_path}\n    D = {dn_path}  usb2_flag_recover.py:182 - usb2_flag_recover_v2.py:182")

    dp = np.fromfile(dp_path, dtype=np.float32)
    dn = np.fromfile(dn_path, dtype=np.float32)
    if dp.size != dn.size:
        print("[!] Longueurs différentes entre D+ et D.  usb2_flag_recover.py:187 - usb2_flag_recover_v2.py:187", file=sys.stderr); sys.exit(1)
    print(f"Échantillons : {dp.size}  usb2_flag_recover.py:188 - usb2_flag_recover_v2.py:188")

    base = estimate_bit_period(dp, dn)
    print(f"[2] Période de bit estimée ≈ {base} échantillons  usb2_flag_recover.py:191 - usb2_flag_recover_v2.py:191")

    best = None  # (score, pol, phase, txt, classes)
    for pol in (+1, -1):  # teste les deux polarités (J/K inversés)
        state = np.sign((dp - dn) * pol).astype(int)
        state[state == 0] = 1
        for phase in range(base):  # essaye toutes les phases d'échantillonnage
            frames = extract_frames_with_state(state, dp, dn, base, phase)
            classes = classify_frames(frames)
            txt = text_from_frames(classes)
            sc = score_text(txt)
            prev = (txt[:60] + "...") if len(txt) > 60 else txt
            print(f"[scan pol={pol:+d} phase={phase:02d}] score={sc} preview='{prev}'  usb2_flag_recover.py:203 - usb2_flag_recover_v2.py:203")
            if (best is None) or (sc > best[0]):
                best = (sc, pol, phase, txt, classes)

    sc, pol, phase, txt, classes = best
    print(f"[3] Choix final : polarité={pol:+d}, phase={phase}, score={sc}  usb2_flag_recover.py:208 - usb2_flag_recover_v2.py:208")

    print("[4] Texte reconstruit :  usb2_flag_recover.py:210 - usb2_flag_recover_v2.py:210")
    print("    " + txt)

    m = re.search(r"(404CTF\{[0-9a-f]{64}\})", txt)
    if m:
        flag = m.group(1)
        print("\n[5] FLAG TROUVÉ ✅  usb2_flag_recover.py:216 - usb2_flag_recover_v2.py:216")
        print("    " + flag)
    else:
        flag = None
        print("\n[5] Aucun flag complet détecté.  usb2_flag_recover.py:220 - usb2_flag_recover_v2.py:220")
        # Affiche quelques trames DATA pour diagnostiquer (longueurs + ASCII)
        shown = 0
        print("[5b] Aperçu de quelques trames DATA :  usb2_flag_recover.py:223 - usb2_flag_recover_v2.py:223")
        for i, (name, fb) in enumerate(classes):
            if name and name.startswith("DATA"):
                pl = data_payload(fb)
                asc = ''.join(chr(b) if is_printable_ascii(b) else '.' for b in pl)
                print(f"{i:03d} {name:6} len={len(pl)} ascii='{asc}'  usb2_flag_recover.py:228 - usb2_flag_recover_v2.py:228")
                shown += 1
                if shown >= 10: break

    out = "usb2_recovered_flag.txt"
    with open(out, "w", encoding="utf-8") as f:
        if txt:  f.write(txt + "\n")
        if flag: f.write(flag + "\n")
    print(f"[6] Résultat écrit dans : {os.path.abspath(out)}  usb2_flag_recover.py:236 - usb2_flag_recover_v2.py:236")

if __name__ == "__main__":
    main()
