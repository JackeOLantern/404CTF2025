
#!/usr/bin/env python3
# template_local.py — Socket.IO **offline** shim (0% réseau)
#
# Objectif : remplacer un client Socket.IO qui se connectait à une URL distante
# par un client **local** qui simule les mêmes événements pour vos scripts.
#
# Il expose la même API minimale que socketio.Client() utilisée dans votre code :
#   - @sio.event decorators : connect(), message(type, data), disconnect()
#   - sio.connect(...), sio.emit(...), sio.wait(), sio.disconnect()
#
# Modes :
#   - **Par défaut (mock local)** : aucune connexion réseau ; on génère des
#     événements "game_state" (score qui monte) puis "flag" à SCORE_TARGET.
#   - **Optionnel (--remote URL)** : si vous voulez quand même parler à un vrai
#     serveur Socket.IO, on bascule sur python-socketio si installé.
#
# Journaux produits (dans le PWD) :
#   - log.csv (tick,action,score) — pour rester compatible avec vos autres scripts
#   - flag.txt — écrit quand le flag est reçu
#
# Exemple :
#   python3 template_local.py                 # 100% local (offline)
#   python3 template_local.py --flag "404CTF{DEMO}" --target 90
#   python3 template_local.py --remote http://127.0.0.1:5000   # (si serveur réel)
#
# Dépendances : aucune en mode local. En mode --remote, nécessite python-socketio.

from __future__ import annotations
import argparse, sys, time, threading, csv
from pathlib import Path

# ----------------------------
# Local shim (no network)
# ----------------------------
class _LocalSIO:
    def __init__(self):
        self._handlers = {}
        self._running = False
        self._thread = None
        self._log_path = Path.cwd() / "log.csv"
        self._flag_path = Path.cwd() / "flag.txt"

    # decorator: @sio.event
    def event(self, func):
        self._handlers[func.__name__] = func
        return func

    # interface compatibility
    def on(self, name):
        def deco(func):
            self._handlers[name] = func
            return func
        return deco

    def _call(self, name, *a, **kw):
        f = self._handlers.get(name)
        if f:
            try:
                return f(*a, **kw)
            except TypeError:
                # Tolérant si la signature diffère légèrement
                return f(*a[:f.__code__.co_argcount])
        return None

    def connect(self, *_args, **_kwargs):
        self._running = True
        self._call("connect")
        # thread de simulation
        self._thread = threading.Thread(target=self._simulate_loop, daemon=True)
        self._thread.start()

    def emit(self, event, data=None):
        # Boucle‐back minimal : si on "emit message", on appelle le handler message
        if event == "message":
            if isinstance(data, (list, tuple)) and len(data) >= 1:
                msg_type = data[0]
                payload = data[1] if len(data) > 1 else None
            elif isinstance(data, dict) and "type" in data:
                msg_type = data["type"]
                payload = data.get("data")
            else:
                msg_type = str(data)
                payload = None
            self._call("message", msg_type, payload)

    def wait(self):
        if self._thread:
            self._thread.join()

    def disconnect(self):
        self._running = False
        self._call("disconnect")

    # ----------------------------
    # Simulation des événements
    # ----------------------------
    def _simulate_loop(self):
        args = _Args.instance()
        score = 0
        tick = 0

        # init log
        with self._log_path.open("w", newline="") as f:
            csv.writer(f).writerow(["tick", "action", "score"])

        # boucle score
        while self._running and score < args.target:
            tick += 1
            score += args.step
            # Événement "game_state" façon backend original
            self._call("message", "game_state", {"score": int(score)})
            with self._log_path.open("a", newline="") as f:
                csv.writer(f).writerow([tick, "-", int(score)])
            time.sleep(args.interval)

        if not self._running:
            return

        # Événement "flag" à l'objectif atteint
        self._call("message", "flag", {"flag": args.flag})
        try:
            self._flag_path.write_text(args.flag, encoding="utf-8")
        except Exception:
            pass

        # Fin propre
        self.disconnect()


# ----------------------------
# Optionnel : backend réel
# ----------------------------
def _make_client(remote: str|None):
    if remote:
        try:
            import socketio  # type: ignore
        except Exception as e:
            print(f"[template_local] python-socketio introuvable : {e}", file=sys.stderr)
            print("[template_local] Bascule en mode local (offline).")
            return _LocalSIO()
        return socketio.Client()  # type: ignore
    return _LocalSIO()


# ----------------------------
# CLI + arguments partagés
# ----------------------------
class _Args:
    _inst = None
    def __init__(self, flag: str, target: int, step: int, interval: float, remote: str|None):
        self.flag = flag
        self.target = target
        self.step = step
        self.interval = interval
        self.remote = remote
    @classmethod
    def instance(cls):
        return cls._inst

def _parse_args():
    ap = argparse.ArgumentParser(description="Client Socket.IO local (offline) simulé.")
    ap.add_argument("--flag", default="404CTF{TR1CH3R_C_EST_PAS_UN_B0N_G4M3_D3S1GN}", help="Flag simulé à l'objectif.")
    ap.add_argument("--target", type=int, default=90, help="Score objectif (déclenche le flag).")
    ap.add_argument("--step", type=int, default=1, help="Incrément de score par tick.")
    ap.add_argument("--interval", type=float, default=0.05, help="Intervalle en secondes entre ticks.")
    ap.add_argument("--remote", default=None, help="URL Socket.IO réelle (facultatif).")
    a = ap.parse_args()
    _Args._inst = _Args(a.flag, a.target, a.step, a.interval, a.remote)
    return _Args._inst

# ----------------------------
# Programme principal
# ----------------------------
def main():
    args = _parse_args()
    sio = _make_client(args.remote)

    # Raccorder les callbacks attendus par votre code existant
    @sio.event
    def connect():
        print("[local-sio] connect()")

    @sio.event
    def message(msg_type, data):
        # Affichage + actions compatibles avec vos autres scripts (log & flag)
        if msg_type == "game_state":
            score = int(data.get("score", 0)) if isinstance(data, dict) else 0
            print(f"[local-sio] game_state: score={score}")
        elif msg_type == "flag":
            flag = data.get("flag") if isinstance(data, dict) else str(data)
            print(f"[local-sio] FLAG: {flag}")
        else:
            print(f"[local-sio] message({msg_type!r}, {data!r})")

    @sio.event
    def disconnect():
        print("[local-sio] disconnect()")

    # Démarrer (local = pas de réseau ; remote = socketio.Client réel)
    if args.remote:
        print(f"[template_local] Connexion réelle à {args.remote}…")
        try:
            sio.connect(args.remote)   # nécessite python-socketio
            sio.wait()
        except Exception as e:
            print(f"[template_local] Échec connexion distante : {e}", file=sys.stderr)
            print("[template_local] Bascule en mode local (offline).")
            # Recréer un client local et démarrer la simulation
            local = _LocalSIO()
            _wire_handlers(local, connect, message, disconnect)
            local.connect()
            local.wait()
    else:
        # 100% local
        sio.connect()
        sio.wait()

def _wire_handlers(client, connect, message, disconnect):
    client._handlers["connect"] = connect
    client._handlers["message"] = message
    client._handlers["disconnect"] = disconnect

if __name__ == "__main__":
    main()
