#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
decrypt_r1_r2.py - déchiffrement de chaîne chiffrée en R1R2 

Affichages intermédiaires :
  • longueur de la chaîne hex,
  • les trois couples (x, y) récupérés,
  • d = b + c et e = b·c,
  • discriminant Δ et racine √Δ,
  • b_int et c_int puis leurs versions ASCII b_str et c_str,
  • le flag final reconstruit.

Aucune dépendance externe, uniquement la bibliothèque standard.
"""

from math import isqrt
import re
import textwrap

# ---------------------------------------------------------------------------
# 1) Chaîne hexadécimale EXACTE (768 caractères / 384 octets = 3×128 octets)
#    - copiée telle quelle depuis le fichier script encrypt.py
# ---------------------------------------------------------------------------
HEX_CIPHER = """
40f1b6e577b2bb6aa703387a15d2738ad50c795972342bdbb4b32946bcf7b72f
bbdfb41884883df6589bf0e1e73a01f4f0d13a60146ac87c146de846bb98407d
8000000000000000000000000000000000000000000000000000000000000000
0c4df9ca82064c5b97e3e5013732439d6139195456b94e581b7a22f1510f926c
4117ca4ed6a10c5d37b5d400dca883d001564774dbbce5c198c5ff83fe7af851
fc3820a17947e71689812f6113dd3893250a14320a8f49c46bde754a188efd30
0000000000000000000000000000000000000000000000000000000000000000
0f6336ee243e9a18cd74b182ff23f87f8bbac8912b57cd3ab25faffcaa18ea39
40d748f2696de5597ec5df6d12826fc2b37d8e926af7a39afe74cb0950460da1
a33112d89029e1a9334ea4c19d36cab027d4b360f240139de4ebd58ebfb05681
8000000000000000000000000000000000000000000000000000000000000000
29e03851f31bd96e478b63347dc9a369a5d0569dc00ffe07cc3ad2d8293a9bf0
"""

# ---------------------------------------------------------------------------
# 2) Nettoyage & vérification
# ---------------------------------------------------------------------------
hex_cipher = re.sub(r"[^0-9a-fA-F]", "", HEX_CIPHER)
if len(hex_cipher) % 2:
    raise ValueError(f"Longueur impaire : {len(hex_cipher)} caractères hex")
print(f"[+] Longueur de la chaîne hex : {len(hex_cipher)} caractères "
      f"({len(hex_cipher)//2} octets)\n")

blob = bytes.fromhex(hex_cipher)
assert len(blob) == 384, "La taille n'est pas 3 * 128 octets"

# ---------------------------------------------------------------------------
# 3) Décapsulage 128 octets → (x, y)
#    Format ci(z, |y|, x)  : 1 bit signe (bit 1022) | 511 bits |y| | 511 bits x
# ---------------------------------------------------------------------------
def unpack(block: bytes) -> tuple[int, int]:
    v = int.from_bytes(block, "big")
    sign  = (v >> 1022) & 1             # bit 1022 (0 = +, 1 = –)
    abs_y = (v >> 511) & ((1 << 511) - 1)
    x     =  v        & ((1 << 511) - 1)
    y = -abs_y if sign else abs_y
    return x, y

blocks = [blob[i*128:(i+1)*128] for i in range(3)]
pairs  = [unpack(b) for b in blocks]

print("=== Couples (x, y) extraits ===")
for idx, (x, y) in enumerate(pairs, 1):
    print(f"  • Pair {idx}:")
    print(f"      x{idx} = {x}")
    print(f"      y{idx} = {y}\n")

# ---------------------------------------------------------------------------
# 4) Résolution : retrouver d = b + c et e = b·c
# ---------------------------------------------------------------------------
(x1, y1), (x2, y2), (x3, y3) = pairs

num = (x1**2 - x2**2) - (y1 - y2)
den = (x1 - x2)
assert num % den == 0, "Division non entière - données corrompues ?"
d = num // den                 # b + c
e = y1 - x1**2 + d*x1          # b · c

# vérification avec le 3ᵉ couple
assert all(x**2 - d*x + e == y for (x, y) in pairs), "Incohérence sur d/e"

print("=== Constantes obtenues ===")
print(f"  d = b + c = {d}")
print(f"  e = b·c   = {e}\n")

# ---------------------------------------------------------------------------
# 5) Racines du polynôme t² − d t + e = 0
# ---------------------------------------------------------------------------
Δ  = d*d - 4*e
sΔ = isqrt(Δ)
assert sΔ*sΔ == Δ, "Δ n'est pas un carré parfait - impossible !"

b_int = (d + sΔ) // 2
c_int = (d - sΔ) // 2
assert b_int > c_int, "Hypothèse b > c violée"

print("=== Racines du polynôme ===")
print(f"  Δ  = {Δ}")
print(f"  √Δ = {sΔ}")
print(f"  b_int = {b_int}")
print(f"  c_int = {c_int}\n")

# ---------------------------------------------------------------------------
# 6) Conversion en ASCII puis ré-entrelacement
# ---------------------------------------------------------------------------
def int_to_ascii(n: int) -> str:
    return n.to_bytes((n.bit_length() + 7) // 8, "big").decode()

b_str = int_to_ascii(b_int)
c_str = int_to_ascii(c_int)

print("=== Moitiés ASCII ===")
print(f"  b_str = {b_str!r}")
print(f"  c_str = {c_str!r}\n")

# indices pairs d’origine → b_str, indices impairs → c_str
flag = "".join(a + b for a, b in zip(b_str, c_str)) \
       + b_str[len(c_str):] + c_str[len(b_str):]

print("=== Flag final ===")
print(f"  {flag}\n")
print("Résolution terminée!")
