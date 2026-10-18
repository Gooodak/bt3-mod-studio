# Guide : jouer à Budokai Tenkaichi 3 sur PC avec nos mods

Ce guide explique, pas à pas, comment installer le jeu sur PC, l'outil **BT3 Mod Studio**, et comment jouer
ensemble en ligne avec les mêmes mods. Pas besoin de savoir programmer.

## Ce qu'il te faut

- Un PC sous **Windows** (64 bits).
- **Ta propre image disque** du jeu, version **USA** (SLUS-21678), en fichier `.iso`. Aucun de nos téléchargements ne
  contient le jeu lui-même : chacun utilise sa propre copie.
- Environ 5 Go de place.

## 1. Choisir l'édition du jeu

Le jeu tourne sur PC grâce au **portage Tenkaichi3Decomp** de z3xox. Il en existe deux éditions :

| | Édition **officielle** | Édition **étendue** (la nôtre) |
|---|---|---|
| D'où elle vient | [github.com/z3xox/Tenkaichi3Decomp](https://github.com/z3xox/Tenkaichi3Decomp/releases) | [github.com/Gooodak/bt3-port-etendu](https://github.com/Gooodak/bt3-port-etendu/releases) |
| Modifier les personnages, attaques, valeurs | oui | oui |
| **Ajouter** des personnages (en plus des 161) | non | oui |
| Jouer **en ligne avec des mods** | non (le menu en ligne refuse un jeu moddé) | oui, entre joueurs qui ont **le même pack** |
| Jouer en ligne sans mods | oui | oui, mais seulement contre des joueurs de l'édition étendue |

**Pour jouer ensemble avec nos mods, prenez tous l'édition étendue.** C'est le même jeu que l'officiel, avec ces
deux ajouts.

## 2. Installer le jeu

1. Télécharge le zip de l'édition choisie (page « Releases » du lien ci-dessus) et décompresse-le dans un dossier,
   par exemple `C:\Jeux\BT3`. Tu obtiens un dossier `Tenkaichi3Decomp`.
2. Lance `Tenkaichi3Decomp-setup.exe`, choisis ton fichier `.iso`. L'installateur vérifie le disque et prépare
   les données du jeu (quelques minutes).
3. Lance `Tenkaichi3Decomp.exe` : le jeu démarre. **F1** ouvre les réglages (manette, image, en ligne).

**Passer de l'officielle à l'étendue** (ou l'inverse) : décompresse le zip de l'autre édition **par-dessus** ton
dossier `Tenkaichi3Decomp` et accepte de remplacer les fichiers. Tes données de jeu et tes sauvegardes restent.

## 3. Installer BT3 Mod Studio

1. Télécharge le zip de l'outil ([github.com/Gooodak/bt3-mod-studio](https://github.com/Gooodak/bt3-mod-studio/releases))
   et décompresse-le **à côté** du dossier `Tenkaichi3Decomp` :
   ```
   C:\Jeux\BT3\
     Tenkaichi3Decomp\        le jeu
     bt3-mod-studio\          l'outil
   ```
2. Double-clique sur **BT3 Mod Studio.exe**. La première fois, il prépare les portraits (quelques secondes).
   S'il ne trouve pas le jeu, il te demande où il est.

Un seul outil sert pour les deux éditions : il voit tout seul laquelle est installée. Les **personnages ajoutés**
ne marchent qu'avec l'édition étendue ; l'outil prévient si ton jeu est l'officielle.

## 4. Faire un pack

Un **pack**, c'est l'ensemble de tes changements. Dans l'outil :

- **Changer un personnage** : choisis-le dans la liste à gauche, puis les onglets :
  - **Personnage** : le remplacer par un autre, son nom dans les menus, ses transformations (R3).
  - **Attaques** : prendre l'attaque d'un autre (« Remplacer par »), renommer, changer les dégâts.
  - **Stats**, **Rafales de ki**, **Déplacements** : vie, ki, puissance, vitesses.
- **Ajouter un personnage** (édition étendue) : bouton **＋ Ajouter un personnage**, choisis de qui il part, puis
  règle-le comme les autres.
- **▶ Appliquer au jeu** (ou F5) : écrit le pack dans le jeu. **Ferme le jeu avant**, relance-le après.
- **Retirer du jeu** : le jeu redevient l'original.

## 5. Partager un pack avec les autres

1. **Partager…** → **Copier le code** : un texte qui commence par `BT3-1-`. Envoie-le (Discord…).
2. Celui qui le reçoit : **Partager…** → colle le code dans **Charger le pack d'un ami** → **Charger ce pack** →
   **Appliquer au jeu**.

Le code contient tout le pack. Il n'y a rien d'autre à envoyer.

## 6. Jouer en ligne ensemble (édition étendue)

1. **Tout le monde applique le même pack** (le même code). L'**empreinte** affichée dans **Partager…** (par exemple
   `874D-CEE7`) doit être la même chez tous.
2. Dans le jeu, **F1 → Online** affiche aussi « Your game data » : comparez-la. Si elle diffère, le match ne
   démarre pas (« different version or different mods ») : quelqu'un n'a pas le même pack, ou pas la même version
   du jeu.
3. Pour se connecter, dans **F1 → Online** : l'un **héberge** (Host) sur un port, l'autre **rejoint** (Join) avec
   l'adresse de l'hôte. Le plus simple : installez tous un réseau virtuel gratuit comme **Radmin VPN** ou
   **Tailscale**, et utilisez l'adresse que ce logiciel donne à l'hôte (sinon, l'hôte doit ouvrir le port dans sa
   box internet).

Les codes de salon du menu « Tenkaichi Budokai Online » ne marchent pas encore avec l'édition étendue.

## 7. Mettre à jour

- **L'outil** : télécharge le nouveau zip et décompresse-le par-dessus l'ancien dossier `bt3-mod-studio`. Tes packs
  enregistrés (`.bt3mod.json`) restent valables.
- **Le jeu** : quand une nouvelle version sort, décompresse-la par-dessus le dossier `Tenkaichi3Decomp`, comme à
  l'installation. Pour jouer en ligne, **tout le monde doit avoir la même version**.
- Après une mise à jour du jeu, ouvre l'outil et refais **Appliquer au jeu**.

## En cas de souci

- **Le jeu ne voit pas mes changements** : le jeu était ouvert pendant « Appliquer au jeu ». Ferme-le, applique,
  relance.
- **Mon personnage ajouté n'apparaît pas** : il faut l'édition étendue (section 1).
- **On n'arrive pas à jouer en ligne** : comparez l'empreinte et la version du jeu ; vérifiez l'adresse et le port
  (ou le VPN).
- **Revenir au jeu d'origine** : **Retirer du jeu** dans l'outil.
