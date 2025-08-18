#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_data.py — Décodage USB1.1 depuis D+ / D− (NRZI + bit stuffing)
- Lecture float64
- Classification J/K/SE0 (seuil auto ou forcé)
- Estimation samples/bit + scan de phase pour recaler l'horloge
- Segmentation par EOP (SE0 pendant 2 bits)
- NRZI -> NRZ, bit unstuffing (skip 0 après 6×1)
- Repérage SYNC = 00000001 (NRZ), regroupement octets LSB-first
- Validation PID (nibble + complément = 0xF)
- Extraction Device Descriptor (18 octets) + flag
"""

import sys
from collections import Counter
import numpy as np

# =======================
# Réglages optionnels
# =======================
FORCE_SAMPLES_PER_BIT = None   # ex: 10 ou None
FORCE_SE0_THR         = None   # ex: 12.0 ou None
PHASE_SCAN            = True
LIST_PACKETS_IF_NONE  = True

# =======================
# Aides / constantes
# =======================
PID_KIND = {
    0x1: "OUT", 0x9: "IN", 0x5: "SOF", 0xD: "SETUP",
    0x3: "DATA0", 0xB: "DATA1", 0x7: "DATA2", 0xF: "MDATA",
    0x2: "ACK",  0xA: "NAK", 0xE: "STALL", 0x6: "NYET",
}
SYNC_NZR = [0,0,0,0,0,0,0,1]   # SYNC en NRZ (00000001)

# =======================
# 1) Lecture des captures
# =======================
def load_diff(plus_path="USB1_D_plus.raw", neg_path="USB1_D_neg.raw"):
    d_plus = np.fromfile(plus_path, dtype=np.float64)
    d_neg  = np.fromfile(neg_path,  dtype=np.float64)
    if len(d_plus) != len(d_neg):
        print("Erreur: longueurs différentes pour D+ et D−. - analyze_data_upd.py:44", file=sys.stderr)
        sys.exit(1)
    return d_plus - d_neg

# =======================
# 2) États J / K / SE0
# =======================
def classify_states(d_diff, force_thr=None):
    absd = np.abs(d_diff)
    auto_thr = float(np.percentile(absd, 50) * 0.25)
    low_thr  = auto_thr if force_thr is None else float(force_thr)
    low_thr  = max(low_thr, 8.0)  # plancher
    state = np.zeros_like(d_diff, dtype=np.int8)
    state[d_diff >  low_thr] =  np.int8(1)   # J
    state[d_diff < -low_thr] =  np.int8(-1)  # K
    return state, low_thr

# =======================
# 3) Estimation samples/bit
# =======================
def estimate_bit_samples(state):
    runs = []
    i = 0
    n = len(state)
    while i < n:
        if state[i] == 0:
            i += 1; continue
        s = state[i]; j = i
        while j < n and state[j] == s:
            j += 1
        runs.append(j - i); i = j
    cnt = Counter(int(round(r)) for r in runs if r < 50)
    if not cnt:
        return 10
    k = cnt.most_common(1)[0][0]
    if k < 5 or k > 40:
        k = 10
    return k

# =======================
# 4) Un état par bit (vote)
# =======================
def majority(chunk: np.ndarray) -> np.int8:
    # Préserve SE0 si clairement majoritaire (sinon on perd l’EOP)
    zeros = int(np.count_nonzero(chunk == 0))
    if zeros / len(chunk) >= 0.60:
        return np.int8(0)
    nz = chunk[chunk != 0]
    if nz.size == 0:
        return np.int8(0)
    return np.int8(1) if float(np.mean(nz)) >= 0.0 else np.int8(-1)

def downsample_with_phase(state: np.ndarray, k: int, phase: int) -> np.ndarray:
    n = (len(state) - phase) // k
    out = np.empty(n, dtype=np.int8)
    base = phase
    for i in range(n):
        sl = state[base + i*k : base + (i+1)*k]
        out[i] = majority(sl)
    return out

# =======================
# 5) Segmentation par EOP
# =======================
def segments_from_eop(bit_states: np.ndarray):
    segs = []
    start = 0
    i = 0
    n = len(bit_states)
    while i < n:
        # EOP = SE0 pendant au moins 2 bits
        if bit_states[i] == 0 and i+1 < n and bit_states[i+1] == 0:
            if i > start:
                seg = bit_states[start:i]
                seg = seg[seg != 0]  # garder J/K
                if len(seg) > 1:
                    segs.append(seg)
            i += 2
            start = i
        else:
            i += 1
    if start < n:
        seg = bit_states[start:]
        seg = seg[seg != 0]
        if len(seg) > 1:
            segs.append(seg)
    return segs

# =======================
# 6) NRZI -> NRZ (USB: 0 => transition, 1 => pas de transition)
# =======================
def nrzi_decode(states: np.ndarray) -> np.ndarray:
    prev = states[0]
    out  = []
    for cur in states[1:]:
        out.append(1 if cur == prev else 0)
        prev = cur
    return np.array(out, dtype=np.uint8)

# =======================
# 7) Bit unstuffing (skip 0 après six 1)
# =======================
def unstuff(bits: np.ndarray) -> np.ndarray:
    out = []
    ones = 0
    i = 0
    L = len(bits)
    while i < L:
        b = int(bits[i])
        out.append(b)
        if b == 1:
            ones += 1
            if ones == 6:
                if i+1 < L and bits[i+1] == 0:
                    i += 1  # saute le 0 "stuffé"
                ones = 0
        else:
            ones = 0
        i += 1
    return np.array(out, dtype=np.uint8)

# =======================
# 8) SYNC + octets LSB-first
# =======================
def find_sync_and_bytes(nrz_bits: np.ndarray):
    bits = nrz_bits.tolist()
    L = len(bits)
    for start in range(0, L - 8):
        if bits[start:start+8] == SYNC_NZR:
            payload = bits[start+8:]
            cut = (len(payload) // 8) * 8
            payload = payload[:cut]
            by = []
            for i in range(0, len(payload), 8):
                byte = 0
                # LSB-first: premier bit => poids 2^0
                for j, b in enumerate(payload[i:i+8]):
                    byte |= (b & 1) << j
                by.append(byte)
            return by
    return []

# =======================
# 9) PID + extraction Device Descriptor
# =======================
def pid_info(by):
    if not by:
        return None
    pid = by[0]
    valid = ((pid & 0xF) ^ (pid >> 4)) & 0xF == 0xF  # nibble + complément => 0xF
    kind  = PID_KIND.get(pid & 0xF, "UNKNOWN")
    return {"pid": pid, "valid": valid, "kind": kind, "bytes": by}

def score_packets(packets) -> int:
    return sum(1 for p in packets if p and p["valid"])

def main():
    d_diff = load_diff()

    # États J/K/SE0
    state, low_thr = classify_states(d_diff, FORCE_SE0_THR)

    # Estimation échantillons/bit
    k_est = estimate_bit_samples(state)
    bit_samples = k_est if FORCE_SAMPLES_PER_BIT is None else int(FORCE_SAMPLES_PER_BIT)
    if bit_samples < 5 or bit_samples > 40:
        bit_samples = 10

    # Essaie k dans {estimé, 10, 9, 11} et phases si PHASE_SCAN
    tried_k = list(dict.fromkeys([bit_samples, 10, 9, 11]))
    best = None

    for k_try in tried_k:
        n_phases = k_try if PHASE_SCAN else 1
        for phase in range(n_phases):
            bits_ph = downsample_with_phase(state, k_try, phase)
            segments = segments_from_eop(bits_ph)
            if not segments:
                continue

            segments_bits = [nrzi_decode(s) for s in segments if len(s) > 1]
            segments_nrz  = [unstuff(b) for b in segments_bits if len(b) >= 8]

            segments_bytes = []
            for s in segments_nrz:
                by = find_sync_and_bytes(s)
                if by:
                    segments_bytes.append(by)

            packets = [pid_info(b) for b in segments_bytes if b]
            packets = [p for p in packets if p and p["valid"]]

            sc = score_packets(packets)
            if best is None or sc > best["score"]:
                best = {"k": k_try, "phase": phase, "packets": packets, "bits": bits_ph, "score": sc}

    packets = best["packets"] if best else []
    k_used  = best["k"] if best else bit_samples
    ph_used = best["phase"] if best else 0

    # Chercher un DATAx avec au moins 1 (PID) + 18 (payload) + 2 (CRC16),
    # ET dont le payload commence par 0x12 0x01 (Device Descriptor).
    found = False
    for p in packets:
        if p["kind"] in ("DATA0", "DATA1") and len(p["bytes"]) >= 1 + 18 + 2:
            payload = p["bytes"][1:-2]  # sans PID, sans CRC16
            if len(payload) >= 18 and payload[0] == 0x12 and payload[1] == 0x01:
                desc = payload[:18]
                print("Device Descriptor (18): - analyze_data_upd.py:252", " ".join(f"{b:02X}" for b in desc))
                bDeviceClass = desc[4]
                idVendor  = desc[8]  | (desc[9]  << 8)  # little-endian
                idProduct = desc[10] | (desc[11] << 8)
                print(f"bDeviceClass=0x{bDeviceClass:02X}  idVendor=0x{idVendor:04X}  idProduct=0x{idProduct:04X} - analyze_data_upd.py:256")

                seq = [desc[4], desc[8], desc[9], desc[10], desc[11]]
                flaghex = "".join(f"{b:02x}" for b in seq)
                print(f"Flag : 404CTF{{{flaghex}}} - analyze_data_upd.py:260")
                found = True
                break

    if not found:
        print(f"[info] Aucun descripteur 18 octets trouvé. - analyze_data_upd.py:265"
              f"(SE0_thr={low_thr:.2f}, k_est={k_est}, k_used={k_used}, phase={ph_used}, paquets valides={len(packets)})")
        if LIST_PACKETS_IF_NONE:
            for i, p in enumerate(packets[:20]):
                head = " ".join(f"{b:02X}" for b in p['bytes'][:8])
                print(f"#{i:02d} PID=0x{p['pid']:02X} {p['kind']:<6} len={len(p['bytes'])} head={head} - analyze_data_upd.py:270")

if __name__ == "__main__":
    main()
