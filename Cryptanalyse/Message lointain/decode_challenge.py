# Charset utilisé dans le chiffrement
charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789{}-!"
n = len(charset)
modulus = n + 1  # 66

# Encrypted message à déchiffrer
encrypted_flag = "828x6Yvx2sOnzMM4nI2sQ"

# Étape 1 : construire la table de log discret
discrete_log_map = {}
for x in range(n):
    y = pow(2, x, modulus)
    discrete_log_map[y] = x

# Étape 2 : déchiffrer
decrypted = []
for char in encrypted_flag:
    if char in charset:
        y_index = charset.index(char)
        if y_index in discrete_log_map:
            x_index = discrete_log_map[y_index]
            decrypted.append(charset[x_index])
        else:
            decrypted.append('?')  # si on ne trouve pas
    else:
        decrypted.append('?')  # caractère inconnu

# Résultat final
flag = ''.join(decrypted)
print("Decrypted FLAG:", flag)
