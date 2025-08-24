Space Traveller — page de substitution (mock)
================================================

Cette page HTML autonome simule le challenge disparu :
- expose `window.game.score` pour les bots Selenium,
- affiche un `<canvas>` (compatible avec les scripts "vision"),
- fait grimper le score automatiquement,
- révèle le flag quand le score atteint 90.

Contenu
-------
- index.html  : la page du faux jeu, utilisable hors-ligne (file://) ou en HTTP local.
- README.txt  : ce fichier d'instructions.

Utilisation rapide (lien web local)
-----------------------------------
Dans le dossier où se trouve `index.html` :
    python3 -m http.server 8000
Puis ouvrez : http://127.0.0.1:8000/index.html

Branchement de vos scripts
--------------------------
Remplacez l'URL cible par `http://127.0.0.1:8000/index.html`.
Le mock fournit:
- `window.game.score` lisible par JavaScript
- un flag inséré dans le DOM quand score ≥ 90
- un <canvas> pour les captures/vision

Changer le flag
---------------
Modifiez la constante FLAG dans `index.html`. Par défaut :
    404CTF{TR1CH3R_C_EST_PAS_UN_B0N_G4M3_D3S1GN}

Note
----
Le mock ne simule pas Socket.IO. Si besoin, créez un petit serveur local Flask-SocketIO/Node qui émet `game_state` et `flag`.
