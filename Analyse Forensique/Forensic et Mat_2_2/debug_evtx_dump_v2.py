#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dump EVTX (Windows Event Log) to XML with robust path handling.
- Par défaut, cherche "CTFCORP_Security.evtx" dans le même dossier que ce script.
- --path permet de préciser un fichier .evtx (relatif au script si non absolu).
- Si le nom exact n'est pas trouvé, propose/choisit le meilleur match parmi les *.evtx du dossier.
- --list pour lister les .evtx détectés à côté du script.
- --limit pour limiter le nombre d'événements.
- --output pour écrire dans un fichier XML (stdout si omis).
"""

from __future__ import annotations
from pathlib import Path
from difflib import get_close_matches
from typing import Optional, List
import argparse
import sys

try:
    # python-evtx (williballenthin/python-evtx)
    from Evtx.Evtx import Evtx
except Exception:
    sys.stderr.write(
        "[!] Impossible d'importer 'python-evtx'. Installez-le avec:\n"
        "    pip install python-evtx\n"
    )
    raise

DEFAULT_NAME = "CTFCORP_Security.evtx"


def choose_best_match(target_name: str, candidates: List[Path], cutoff: float = 0.6) -> Optional[Path]:
    """Retourne le nom le plus proche dans candidates (via difflib.get_close_matches)."""
    names = [c.name for c in candidates]
    matches = get_close_matches(target_name, names, n=1, cutoff=cutoff)
    if matches:
        best = next((c for c in candidates if c.name == matches[0]), None)
        return best
    return None


def resolve_evtx_path(path_arg: Optional[str]) -> Path:
    """
    Résout le chemin du .evtx :
    - Si --path est fourni : relatif au dossier du script si non absolu ; sinon tentative de "best match".
    - Sinon : on préfère DEFAULT_NAME à côté du script ; sinon tentative de "best match" sur *.evtx.
    """
    script_dir = Path(__file__).resolve().parent
    if path_arg:
        candidate = Path(path_arg)
        if not candidate.is_absolute():
            candidate = (script_dir / candidate).resolve()
        if candidate.exists():
            return candidate

        evtx_files = sorted(script_dir.glob("*.evtx"))
        best = choose_best_match(candidate.name, evtx_files)
        if best:
            sys.stderr.write(
                f"[i] Fichier '{candidate.name}' introuvable. Utilisation du meilleur match: '{best.name}'.\n"
            )
            return best

        raise FileNotFoundError(
            f"Fichier '{candidate}' introuvable. "
            f"Disponibles: {[p.name for p in evtx_files] or 'aucun .evtx détecté dans ce dossier.'}"
        )

    # Pas de --path : tenter le DEFAULT_NAME
    default = (script_dir / DEFAULT_NAME).resolve()
    if default.exists():
        return default

    # Sinon, tenter un meilleur match sur *.evtx
    evtx_files = sorted(script_dir.glob("*.evtx"))
    if len(evtx_files) == 1:
        sys.stderr.write(f"[i] Aucun '{DEFAULT_NAME}'. Utilisation de '{evtx_files[0].name}'.\n")
        return evtx_files[0]

    best = choose_best_match(DEFAULT_NAME, evtx_files)
    if best:
        sys.stderr.write(
            f"[i] '{DEFAULT_NAME}' introuvable. Utilisation du meilleur match: '{best.name}'.\n"
        )
        return best

    raise FileNotFoundError(
        f"Aucun fichier EVTX par défaut trouvé. "
        f"Disponibles: {[p.name for p in evtx_files] or 'aucun .evtx détecté dans ce dossier.'}"
    )


def dump_evtx_to_xml(evtx_path: Path, output: Optional[Path], limit: Optional[int]) -> int:
    """
    Ouvre le EVTX et écrit chaque record en XML vers stdout ou vers un fichier.
    Retourne le nombre d'événements écrits.
    """
    count = 0
    with Evtx(str(evtx_path)) as log:
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("w", encoding="utf-8", newline="\n") as f:
                f.write('<?xml version="1.0" encoding="utf-8"?>\n<Events>\n')
                for rec in log.records():  # <-- records() est une méthode
                    f.write(rec.xml())
                    f.write("\n")
                    count += 1
                    if limit and count >= limit:
                        break
                f.write("</Events>\n")
        else:
            print('<?xml version="1.0" encoding="utf-8"?>')
            print("<Events>")
            for rec in log.records():  # <-- records() est une méthode
                print(rec.xml())
                count += 1
                if limit and count >= limit:
                    break
            print("</Events>")
    return count


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Dump EVTX to XML avec gestion robuste des chemins.")
    parser.add_argument("--path", "-p", help="Chemin vers le fichier .evtx (relatif au script si non absolu).")
    parser.add_argument("--output", "-o", help="Fichier de sortie XML (stdout si omis).")
    parser.add_argument("--limit", "-n", type=int, help="Nombre maximal d'événements à dumper.")
    parser.add_argument("--list", action="store_true", help="Lister les .evtx à côté du script et quitter.")
    args = parser.parse_args(argv)

    script_dir = Path(__file__).resolve().parent
    if args.list:
        evtx_files = sorted(script_dir.glob("*.evtx"))
        if not evtx_files:
            print("Aucun .evtx détecté à côté du script.")
        else:
            print("EVTX disponibles :")
            for p in evtx_files:
                print(" -", p.name)
        return 0

    try:
        evtx_file = resolve_evtx_path(args.path)
    except FileNotFoundError as e:
        sys.stderr.write(f"[!] {e}\n")
        return 2

    output_path = Path(args.output).resolve() if args.output else None

    try:
        total = dump_evtx_to_xml(evtx_file, output_path, args.limit)
        sys.stderr.write(f"[✓] Événements écrits : {total}\n")
        return 0
    except FileNotFoundError:
        sys.stderr.write(f"[!] Fichier introuvable: {evtx_file}\n")
        return 2
    except KeyboardInterrupt:
        sys.stderr.write("\n[!] Interrompu par l'utilisateur.\n")
        return 130
    except Exception as e:
        sys.stderr.write(f"[!] Erreur inattendue: {e}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
