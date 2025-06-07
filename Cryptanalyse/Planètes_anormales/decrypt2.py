from tqdm import tqdm
import ast
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Util.number import long_to_bytes
from Crypto.Random import random as rd
import os

# === Courbe ECC ===
class Curve:
    def __init__(self, a, b, p, g):
        self.a = a
        self.b = b
        self.p = p
        self.g = g

    def addPoints(self, P, Q):
        a, p = self.a, self.p
        if P == (0, 0): return Q
        if Q == (0, 0): return P
        x1, y1, x2, y2 = P[0], P[1], Q[0], Q[1]
        if x1 == x2 and y1 == (-y2 % p): return (0, 0)
        if x1 == x2 and y1 == y2:
            m = (3 * x1 ** 2 + a) * pow(2 * y1, -1, p) % p
        else:
            m = (y2 - y1) * pow(x2 - x1, -1, p) % p
        x3 = (m ** 2 - x1 - x2) % p
        y3 = (m * (x1 - x3) - y1) % p
        return x3, y3

    def pointMultiplication(self, k, P):
        R = (0, 0)
        Q = P
        while k > 0:
            if k & 1:
                R = self.addPoints(R, Q)
            Q = self.addPoints(Q, Q)
            k >>= 1
        return R

# === Paramètres de la courbe custom ===
curve =  Curve(0xbb0480e1f010abb2e69e7d72df5d75a23a15bc73710df25b6da04121f904e4f5,
                     0xfa2bddcca24c1d80baf26cb1e1f04cf78e995c675543c9692e959f83b470a03,
                     0xf7fda1b2f0c9ea506e8a125766fd9e5046fd5716630c84f526fea8ce10497829,
                     (0x735d07d96821ec8bff37eb23c31081ea526ddc10abe22375518c44e043a39db0,
                      0x97e570cf7c177584ddd036d9181a3f5f83307f60c92b539a2d4f479d9c9ad4bd)
                     )

# === Point Q = d·G donné ===
Q_target = (
    79944403612648084410282504217789823912187113913937547911584848200371745063162,
    67086762406249444334512715653977941111183186976781269540452303526058470677584
)

def find_order2(curve, G, max_n=2**30):
    P = G
    for n in range(1, max_n):
        if P == (0, 0):
            return n
        P = curve.addPoints(P, G)
    return None  # si ordre > max_n

def find_order(curve, G, max_check=1_000_000):
    P = G
    for i in range(1, max_check):
        P = curve.addPoints(P, G)
        if P == (0, 0):
            return i + 1
    return None

def order():
    order = find_order(curve, curve.g)
    if order:
        print(f"[+] Ordre du point G : {order}")
    else:
        print("[-] G a un grand ordre (ou supérieur à max_n)")

def attQ():
    G = curve.g
    Q1 = curve.pointMultiplication(rd.randint(2, curve.p - 1), G)
    Q2 = curve.pointMultiplication(rd.randint(2, curve.p - 1), G)
    print(f"Q1={Q1}\nQ2={Q2}")
    print(Q1 == Q2)  # Si True, alors `d` est fixé !!!

order()