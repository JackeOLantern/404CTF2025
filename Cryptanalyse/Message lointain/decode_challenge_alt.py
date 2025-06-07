charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789{}-!"
n = len(charset)
modulo = n + 1  # 66

# Créer la table d'inversion
decrypt_map = {}
for x in range(n):
    y = pow(2, x, modulo)
    if y < n:
        decrypt_map[charset[y]] = charset[x]

# Chaine chiffrée extraite du script
encrypted_flag = "828x6Yvx2sOnzMM4nI2sQ"

# Déchiffrement
decrypted = ''.join(decrypt_map[c] for c in encrypted_flag)
print("DECRYPTED FLAG :", decrypted)
