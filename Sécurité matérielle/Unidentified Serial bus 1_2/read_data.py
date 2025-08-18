import numpy as np
import matplotlib.pyplot as plt

# Lecture des fichiers
d_plus = np.fromfile("USB1_D_plus.raw", dtype=np.float64)
d_neg = np.fromfile("USB1_D_neg.raw", dtype=np.float64)

# Calcul du signal différentiel (D+ - D−)
d_diff = d_plus - d_neg

# Affichage
plt.figure()
plt.plot(d_plus, label="D+")
plt.plot(d_neg, label="D−")
plt.plot(d_diff, label="D+ - D−")
plt.legend()
plt.title("Signaux USB capturés")
plt.xlabel("Échantillons")
plt.ylabel("Tension (V ?)")
plt.grid()
plt.show()
