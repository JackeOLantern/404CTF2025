from pwn import *

# === Paramètres du serveur ===
HOST = "challenges.404ctf.fr"
PORT = 30169


def getFlagEncored(p):
    # === Lire jusqu'à l'invite "(2) ? >" et envoyer "2" pour obtenir le flag chiffré ===
    p.recvuntil(b"(2) ? >")
    p.sendline(b"2")
    line = p.recvline().decode()
    blocks = []
    # === Extraction du flag chiffré ===
    if "> " in line:
        flag_enc = line.split("> ")[1].strip()
        print(f"[+] line : {line}")
        print(f"[+] Flag chiffré : {flag_enc}")
        # Découpe en blocs de 16 octets (32 hex chars)
        blocks = [flag_enc[i:i+32] for i in range(0, len(flag_enc), 32)]

        for idx, block in enumerate(blocks):
            print(f"Bloc {idx+1} : {block}")
        return blocks
    else:
        print("[!] Erreur de récupération du flag.")
        exit()

# Dictionnaire pour stocker les résultats en cache

def sendTestValue(p, test, cache):
    if test in cache:
        #print(f"Valeur trouvée dans le cache pour test = {test}")
        return cache[test]

    try:
        bytes.fromhex(test)
    except:
        print("[-] Format hex invalide.")
        return None
    # Envoyer '1' pour mode chiffrage
    p.recvuntil(b"(2) ? >")
    #print("[-] send 1.  -> chiffrer")
    p.sendline(b"1")
    p.recvuntil(b"chiffrer >")
    #print("[-] -value ", test, " - ", len(test))

    p.sendline(test.encode())

    # Lire le résultat du chiffrage
    line = p.recvline().decode()
    if "> " in line:
        result = line.split("> ")[1].strip()
        # Stocker le résultat dans le cache
        cache[test] = result
        return result
    else:
        print("[!] Pas de réponse valide : ", line)
    return None

def main():
    cache = {}
    # === Connexion initiale ===
    p = remote(HOST, PORT)
    blocks = getFlagEncored(p)
    bl = 0
    bloc = bytes.fromhex(blocks[bl])
    pos = 0
    cumulflag = ""
    while pos < 16:
        c = []
        try:
            for b in range(2):
                test = "00" * pos + bytes([b]).hex() + "00" * (15 - pos)  # 1 byte fixé, le reste à 0
                result = sendTestValue(p, test, cache)
                c.append( bytes.fromhex(result))
                print(f"[+] Chiffré : {test} - {result}")
            print("\nDifférences byte par byte :")
            for i, (b1, b2) in enumerate(zip(c[0], c[1])):
                if b1 != b2:
                    print(f"Byte pos {pos} -> #{i}: {b1:02x} → {b2:02x}  |  flagCrypte[{i}] = {bloc[i]:02x}")
                    for b in range(0, 256):
                        test = "00" * pos + bytes([b]).hex() + "00" * (15 - pos)  # 1 byte fixé, le reste à 0
                        result = sendTestValue(p, test, cache)
                        cipher = bytes.fromhex(result)
                        ci = cipher[i]
                        if ci == bloc[i]:
                            cumulflag += chr(b)
                            print(f"✔️  flag[{pos}] = {b:#02x} ('{chr(b)}') : {cumulflag}")
                            break
        
            pos += 1
            if pos > 15 and bl < 3:
                pos = 0
                bl+=1
                print("Changement de bloc :", bl)
                p.close()
                cache = {}
                p = remote(HOST, PORT)
                blocks = getFlagEncored(p)
                bloc = bytes.fromhex(blocks[bl])

        except EOFError:
            print("[-] Déconnexion détectée. Tentative de reconnexion et purge du cache...")
            time.sleep(1)  # Attendre un peu avant de se reconnecter
            cache = {}
            p = remote(HOST, PORT)
            blocks = getFlagEncored(p)
            bloc = bytes.fromhex(blocks[bl])
        except Exception as e:
            print(f"[-] Erreur inattendue: {e}")
            return None



# === Fermer proprement ===
main()
p.close()