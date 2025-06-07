#!/usr/bin/env python3
"""
decrypt_r1_r2.py  - Résolution en : R1R2 

Affichages :
  • taille du blob + aperçu hex
  • z, |y|, x pour chaque bloc
  • debug pour chaque combinaison valide
  • liste finale des flags candidats
"""

from itertools import product
from math import isqrt
import re, sys, textwrap

# ---------------------------------------------------------------------------#
# 1)  Ciphertext hexadécimal (3 blocs de 128 octets)                          #
# ---------------------------------------------------------------------------#
HEX_CIPHER = """
40f1b6e577b2bb6aa703387a15d2738ad50c795972342bdbb4b32946bcf7b72f
bbdfb41884883df6589bf0e1e73a01f4f0d13a60146ac87c146de846bb98407d
8000000000000000000000000000000000000000000000000000000000000000
0c4df9ca82064c5b97e3e5013732439d6139195456b94e581b7a22f1510f926c
4117ca4ed6a10c5d37b5d400dca883d001564774dbbce5c198c5ff83fe7af851
fc3820a17947e71689812f6113dd3893250a14320a8f49c46bde754a188efd30
0000000000000000000000000000000000000000000000000000000000000000
0f6336ee243e9a18cd74b182ff23f87f8bbac8912b57cd3ab25faffcaa18ea3
940d748f2696de5597ec5df6d12826fc2b37d8e926af7a39afe74cb0950460da
1a33112d89029e1a9334ea4c19d36cab027d4b360f240139de4ebd58ebfb0568
1800000000000000000000000000000000000000000000000000000000000000
029e03851f31bd96e478b63347dc9a369a5d0569dc00ffe07cc3ad2d8293a9bf0
"""

# ---------------------------------------------------------------------------#
# 2)  Nettoyage + conversion binaire                                          #
# ---------------------------------------------------------------------------#
hex_cipher = re.sub(r"[^0-9a-fA-F]", "", HEX_CIPHER)
if len(hex_cipher) % 2:
    hex_cipher = "0" + hex_cipher                       # sécurité
blob = bytes.fromhex(hex_cipher)

print(f"[+] Longueur blob : {len(blob)} octets")
print("[+] Aperçu hex (64 premiers caractères) :", hex_cipher[:64], "...\n")

if len(blob) != 384:
    sys.exit(f"Le blob doit faire 384 octets, pas {len(blob)}.")

# ---------------------------------------------------------------------------#
# 3)  Décodage bloc → (z, |y|, x)                                             #
# ---------------------------------------------------------------------------#
def unpack(block: bytes):
    v = int.from_bytes(block, "big")
    z     = (v >> 1022) & 1
    abs_y = (v >> 511) & ((1 << 511) - 1)
    x     =  v & ((1 << 511) - 1)
    return z, abs_y, x

triplets = [unpack(blob[i:i+128]) for i in range(0, 384, 128)]

print("=== Triplets extraits ===")
for i, (z, ay, x) in enumerate(triplets, 1):
    print(f"Bloc {i} : z={z}, |y|≈{hex(ay)[:18]}…, x≈{hex(x)[:18]}…")
print()

# On ne garde que (|y|, x) pour le calcul ; le signe sera testé plus loin
(a1,x1),(a2,x2),(a3,x3) = [(ay,x) for _,ay,x in triplets]

# ---------------------------------------------------------------------------#
# 4)  Fonction d’essai d’une combinaison de signes                            #
# ---------------------------------------------------------------------------#
def try_combination(y1, y2, y3):
    num = (x1*x1 - x2*x2) - (y1 - y2)
    den = x1 - x2
    if num % den:
        return None
    d = num // den
    e = y1 - x1*x1 + d*x1
    if x3*x3 - d*x3 + e != y3:
        return None
    delta = d*d - 4*e
    s = isqrt(delta)
    if s*s != delta:
        return None
    b, c = (d + s)//2, (d - s)//2
    if not (b > c > 0):
        return None
    return b, c, d, e, delta

to_ascii = lambda n: n.to_bytes((n.bit_length()+7)//8, "big").decode()

flags = []
print("=== Recherche des combinaisons ===")
for s1, s2, s3 in product((1, -1), repeat=3):
    result = try_combination(s1*a1, s2*a2, s3*a3)
    if not result:
        continue
    b_int, c_int, d, e, delta = result
    b_str, c_str = to_ascii(b_int), to_ascii(c_int)
    flag = "".join(a+b for a,b in zip(b_str, c_str)) \
           + b_str[len(c_str):] + c_str[len(b_str):]

    print(f"[✓] Signes {(s1,s2,s3)}  →  d={d}, e={e}")
    print(f"    Δ={delta}  b={b_int}  c={c_int}")
    print(f"    b_str='{b_str}'  c_str='{c_str}'")
    print(f"    FLAG Candidat : {flag}\n")
    flags.append(flag)

if not flags:
    sys.exit("Aucune combinaison ne fonctionne !")

# Filtre optionnel : motif simple
regex = re.compile(r"^404CTF\{[0-9a-z_]+\}$")
flags = [f for f in flags if regex.match(f)] or flags

print("=== Résultat(s) final(aux) ===")
for f in flags:
    print("FLAG =", f)
