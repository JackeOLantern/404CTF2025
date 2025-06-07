import socket
from sympy import symbols, Poly, solve
import sys

def recv_until(sock, delimiter=b"\n"):
    data = b""
    while not data.endswith(delimiter):
        chunk = sock.recv(1)
        if not chunk:
            break
        data += chunk
    print(data.decode(errors="ignore"), end="")
    return data

def print_progress(current, total, bar_length=40):
    progress = int(bar_length * current / total)
    bar = "[" + "#" * progress + "-" * (bar_length - progress) + "]"
    sys.stdout.write(f"\r{bar} {current}/{total}")
    sys.stdout.flush()

def solve_entretien_rh_socket():
    host = "challenges.404ctf.fr"
    port = 30069

    print(f"Connexion à {host}:{port}")
    s = socket.create_connection((host, port))
    s.settimeout(5)

    # Lire toute l’intro d’un coup jusqu’à la question
    intro = b""
    while b"Comment vous appelez-vous" not in intro:
        chunk = s.recv(1024)
        if not chunk:
            break
        intro += chunk
        print(chunk.decode(errors="ignore"), end="")

    name = "Galactix"
    print(f"\n>>> Envoi du prénom : {name}\n")
    s.sendall((name + "\n").encode())

    for i in range(1, 101):
        print_progress(i, 100)

        recv_until(s, b"x + y + z = ")
        s1 = int(recv_until(s).strip())

        recv_until(s, b"x^2 + y^2 + z^2 = ")
        s2 = int(recv_until(s).strip())

        recv_until(s, b"x^3 + y^3 + z^3 = ")
        s3 = int(recv_until(s).strip())

        # Newton
        p1 = s1
        p2 = (s1**2 - s2) // 2
        p3 = (s1**3 - 3*s1*s2 + 2*s3) // 6

        x = symbols('x')
        poly = Poly(x**3 - p1*x**2 + p2*x - p3)
        roots = solve(poly, x)
        roots = sorted(int(r) for r in roots)

        answer = f"{roots[0]},{roots[1]},{roots[2]}"
        recv_until(s, b"? ")
        s.sendall(answer.encode() + b"\n")

    # Lecture finale
    print("\n\n>>> Lecture finale (flag)")
    final = b""
    try:
        while True:
            part = s.recv(4096)
            if not part:
                break
            final += part
    except socket.timeout:
        pass

    decoded = final.decode()
    print(decoded)

    with open("flag.txt", "w") as f:
        f.write(decoded)

    print("\n✅ Flag enregistré dans flag.txt")
    s.close()

if __name__ == "__main__":
    solve_entretien_rh_socket()

