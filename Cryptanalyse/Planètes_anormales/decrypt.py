from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
from Crypto.Util.number import long_to_bytes
import base64

# === Paramètres ===
# secret d
d = 0x268dc922041bc83705b0f8b79a6c8c2ce252a7608271eb4b43b46f3db8e2027b  # <-- données par sagemath
username = "me"         # <-- le nom du début
ciphertext = bytes.fromhex("23c21181c74b0b2084ec1232606ba05b59374f309f849de74530800039abcbedf277d05e6c8ef29c871b78c908297107")  # <-- la chaine crtptée du serveur netcat

# === Clé AES et IV ===
key = pad(long_to_bytes(d), 32)[:32]
iv  = pad(username.encode(), 16)[:16]

# === Déchiffrement ===
cipher = AES.new(key, AES.MODE_CBC, iv)
plaintext_padded = cipher.decrypt(ciphertext)

try:
    plaintext = unpad(plaintext_padded, 16)
    print("[+] Message déchiffré :", plaintext.decode())
except ValueError:
    print("[-] Mauvais padding ou d/IV incorrect")