import os
import random
import time

print("Pour pouvoir être recrute dans l'equipe du gorfou galactique, il va falloir passer un petit entretiens d'embauche...")
print("Rien de bien mechant pour un agent chevrone comme vous...")

def getRand():
    return int.from_bytes(os.urandom(16), "big")

prenom = list(input("Comment vous appelez-vous ? "))
random.shuffle(prenom)
prenom = "".join(prenom)

questions_rh = [
    "Si vous étiez une photocopieuse, comment réagiriez-vous à une surcharge papier émotionnelle",
    "Un lama rentre dans la salle de réunion et réclame un Beamer. Que faites-vous",
    "Décrivez vos competences en télépathie sur une echelle de 1 à 'je connais déjà votre reponse'",
    "Combien de pingouins peut-on faire rentrer dans une théière sans enfreindre la charte éthique de l'entreprise",
    "Votre manager se transforme soudainement en moine tibétain et ne parle plus que par enigmes. Comment menez-vous à bien votre projet",
    "Vous êtes coincé dans un ascenseur avec votre alter ego du futur qui vous juge. Quel est votre plan de survie mentale",
    "Si vous deviez convaincre un pot de yaourt de vous accorder une promotion, quel serait votre discours",
    "Quel est votre plus grand échec professionnel impliquant une chèvre et un vidéoprojecteur",
    "Un stagiaire affirme être la reincarnation de Napoléon. Le croyez-vous. Pourquoi",
    "Si on vous donnait le pouvoir de rendre invisible un seul objet au bureau, que choisiriez-vous (et pourquoi la machine à café)",
    "Comment voyez vous votre vie dans 48 ans",
    "Votre collègue de bureau vous mord le doigt de pied, que faites vous"]

for _ in range(100):
    x, y, z = sorted(getRand() for _ in range(3))
    print(f"x + y + z = {x + y + z}")
    print(f"x^2 + y^2 + z^2 = {x**2 + y**2 + z**2}")
    print(f"x^3 + y^3 + z^3 = {x**3 + y**3 + z**3}")

    try:
        t1 = time.time()
        nx, ny, nz = list(map(int, input(random.choice(questions_rh) + " ? ").split(",")))
        t2 = time.time()

        assert (x, y, z) == (nx, ny, nz)
        assert t2 - t1 < 5
    except:
        print(f"Merci beaucoup {prenom}, c'etait très challengeant, on transmet votre CV ASAP.")
        exit()

print(f"Votre profil est strictement parfait !!\nNous vous proposons un magnifique poste de {open('flag.txt', 'r').read()} a 1,2 euro de l'heure !")