#!/usr/bin/env python3
"""
Script tout-en-un pour :
1. Lancer GQRX en mode lecture IQ
2. Démoduler en Narrow FM centrée sur 135kHz
3. Capturer le flux audio via UDP
4. Le convertir et le passer à multimon-ng pour décoder POCSAG
5. Afficher le flag intercepté
"""

import subprocess
import time
import shlex

def launch_gqrx(iq_file):
    """
    Lance GQRX en mode lecture de fichier IQ via ligne de commande.
    L'utilisateur devra configurer dans l'interface :
     - Input Control → Enable UDP server (port 7355)
     - Narrow FM, bande, centrage approprié
    """
    cmd = f"gqrx -r {iq_file}"
    print(f"[+] Lance GQRX avec : {cmd}  Untitled1:23  .py:23  decode_pocsg.py:23 - decode_pocsag.py:23")
    return subprocess.Popen(shlex.split(cmd))

def start_pocsag_pipe():
    """
    Monte la commande shell qui :
    - écoute UDP en entrée
    - pipe via sox pour conversion d'échantillonnage
    - décode avec multimon-ng (POCSAG à 512, 1200, 2400 bauds)
    Retourne le subprocess lancé
    """
    cmd = (
        "nc -l -u -p 7355 | "
        "sox -t raw -esigned-integer -b16 -r 48000 - -t raw -esigned-integer -b16 -r 22050 - | "
        "multimon-ng -t raw -a POCSAG512 -a POCSAG1200 -a POCSAG2400 -f alpha -e --timestamp -"
    )
    print(f"[+] Lance le pipeline entrée UDP → sox → multimonng :\n    {cmd}  Untitled1:39  .py:39  decode_pocsg.py:39 - decode_pocsag.py:39")
    return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def main():
    iq_file = "chall.iq"
    print("[*] Script démarrage...  Untitled1:44  .py:44  decode_pocsg.py:44 - decode_pocsag.py:44")
    gqrx_proc = launch_gqrx(iq_file)
    time.sleep(2)  # Temps pour initialiser GQRX (modifiable selon ta machine)

    pipe_proc = start_pocsag_pipe()

    print("[*] En attente du décodage POCSAG...\n  Untitled1:50  .py:50  decode_pocsg.py:50 - decode_pocsag.py:50")
    try:
        # Lecture continue de la sortie
        for line in pipe_proc.stdout:
            print(line, end="")
            if "404CTF{" in line:
                print("\n[+] Flag détecté, fin du script.  Untitled1:56  .py:56  decode_pocsg.py:56 - decode_pocsag.py:56")
                break
    except KeyboardInterrupt:
        print("\n[!] Interruption manuelle.  Untitled1:59  .py:59  decode_pocsg.py:59 - decode_pocsag.py:59")

    print("[*] Nettoyage...  Untitled1:61  .py:61  decode_pocsg.py:61 - decode_pocsag.py:61")
    gqrx_proc.terminate()
    pipe_proc.terminate()
    print("[*] Terminé.  Untitled1:64  .py:64  decode_pocsg.py:64 - decode_pocsag.py:64")

if __name__ == "__main__":
    main()
