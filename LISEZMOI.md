# BT3 Mod Studio

Un petit outil pour modifier les personnages de **Dragon Ball Z Budokai Tenkaichi 3** joué avec le port PC
**Tenkaichi3Decomp** (version USA du disque, SLUS-21678).

## Installation

1. Mets le dossier `bt3-mod-studio` à côté du dossier `Tenkaichi3Decomp` (celui qui contient `Tenkaichi3Decomp.exe`).
   Sinon l'outil te demandera une seule fois où se trouve le jeu, et s'en souviendra.
2. Double-clique sur **BT3 Mod Studio.exe**. Rien d'autre à installer : Python est inclus dans le programme (le
   dossier `runtime` à côté de l'exe, à garder avec lui).

À la toute première ouverture, l'outil prépare les portraits des personnages et la recherche par attaque (quelques
secondes), puis les grandes illustrations, tranquillement, pendant la première minute d'utilisation. Ensuite il
s'ouvre en moins d'une seconde. Ces fichiers sont rangés dans `%LOCALAPPDATA%\BT3 Mod Studio` (ils viennent de ton
jeu : ils ne partent pas avec l'outil quand tu le donnes à un ami).

## La fenêtre

- **À gauche**, les 161 personnages avec leur portrait. Tape un nom, une attaque (« kamehameha ») ou un numéro pour
  chercher. **Modifiés** ne montre que les personnages changés dans ton pack.
- **＋ Ajouter un personnage** (sous la recherche) crée un personnage **en plus** dans la grille, à partir d'un
  personnage du jeu : il ne remplace personne. Il apparaît en bas de la liste (« ＋ … ») et se règle comme les
  autres : son nom et sa forme (onglet Personnage), ses attaques, ses valeurs. Il demande l'**édition étendue** du
  port (plus bas).
- **Mods de personnages…** (sous « Ajouter un personnage ») : importer un personnage fait par la communauté (un
  dossier ou un zip de fichiers du jeu : « Vegeta(1733).unk », « …_1p.pak »…). L'outil reconnaît chaque fichier,
  devine le personnage dont il part, et l'installe dans le dossier `characters` du jeu ; il apparaît en plus dans la
  grille (édition étendue). La même fenêtre liste les mods installés, les retire, et donne leur **empreinte** : pour
  jouer en ligne, elle doit être la même chez tous.
- **À droite**, le personnage choisi tel qu'il apparaît à l'écran de sélection du jeu.
- **Au milieu**, son nom, un résumé (vie, ki, blast stocks, Ultime) et les onglets :
  - **Personnage** :
    - **Remplacer ce personnage** : l'emplacement devient une copie complète d'un autre personnage (modèle,
      animations, attaques, stats, voix, portraits des menus). Par exemple, Pilaf Machine remplacé par Vegeta.
    - **Nom dans les menus** : le nom et la forme affichés à l'écran de sélection (30 caractères au plus).
    - **Transformations en combat** : en quoi le personnage se transforme avec R3 (R3 seul, ou R3 + une direction :
      relâche R3 en gardant la direction) et le coût en barres de blast. Pour une copie, c'est automatique : elle
      garde les transformations du personnage copié, et vise les autres copies du même pack (Pilaf Machine → Vegeta
      et sa Fusion → Super Vegeta : la copie de Vegeta devient la copie de Super Vegeta, puis revient). Le
      personnage visé doit être débloqué dans ta sauvegarde, sinon le jeu refuse la transformation.
    - **Formes à l'écran de sélection** : les formes qu'on choisit après avoir choisi la case (Goku : normal, Super
      Saiyan, SSJ2…). Pour une copie, la case reprend automatiquement les formes du personnage copié.
  - **Attaques** : chaque attaque spéciale (Blast 1, Blast 2, Ultime) avec son nom affiché (anglais pour le jeu US,
    français), ses valeurs (dégâts, coût en ki, vitesse et guidage du projectile…) et **Remplacer par** : prendre
    l'attaque d'un autre personnage, avec son animation, ses effets et sa caméra. Un Blast 1 se remplace par un
    Blast 1 (par exemple l'Explosive Wave de Vegeta à la place du Taiyoken de Goku), un Blast 2 ou l'Ultime par un
    Blast 2 ou un Ultime. Si une attaque ne peut pas aller sur ce personnage (animations déjà prises, ou effets trop
    lourds pour la place que le jeu leur réserve), l'outil le dit tout de suite.
  - **Stats** : vie, ki au départ, blast stocks, résistance, corps à corps, ki et Max Power.
  - **Rafales de ki** : un tableau des 13 rafales (passe la souris sur une case pour son unité et sa valeur
    d'origine).
  - **Déplacements** : les 20 vitesses, avec un bouton pour toutes les multiplier d'un coup.
- Une valeur modifiée devient **jaune**, avec sa valeur d'origine et **↺ remettre** à côté (clic droit dans les
  tableaux). Les valeurs sont traduites dans les unités du jeu : **10 000 = 1 barre de vie**, **20 000 = 1 barre de
  ki**.
- Pour choisir un personnage (remplacement, attaque reprise, transformation, forme), une petite fenêtre s'ouvre avec
  la recherche et les portraits : double-clic pour choisir.
- **Taille du texte** (en bas à droite, **A−** / **A+**, ou Ctrl + molette) : de 90 % à 160 %, retenue pour la
  prochaine fois. Quand la fenêtre est trop étroite (texte agrandi, petit écran), la grande illustration se replie
  pour laisser la place aux réglages ; elle revient quand on élargit la fenêtre.
- **Au clavier** : **F1** montre tous les raccourcis. Ctrl+F pour chercher, Ctrl+↑ / Ctrl+↓ pour passer d'un
  personnage à l'autre, Ctrl+1 à Ctrl+5 pour les onglets ; Tab passe d'un bouton à l'autre (le bouton choisi a une
  bordure orange) et Espace ou Entrée le presse.
- La molette fait défiler la page même au-dessus d'une liste ou d'un nombre : elle ne change jamais une valeur sans
  le vouloir.

## Appliquer, partager, revenir en arrière

- **▶ Appliquer au jeu** (ou F5) écrit les fichiers modifiés dans `Tenkaichi3Decomp/gamedata/mods/`. Le jeu les
  utilise à la place des originaux. Les fichiers originaux ne sont **jamais** modifiés. Ferme le jeu avant
  d'appliquer, puis relance-le. En haut, **● Non appliqué** rappelle que des changements ne sont pas encore dans le
  jeu ; **✓ Appliqué** que le jeu utilise ce pack tel qu'il est.
- La première fois qu'un pack change un nom ou une case des menus, l'outil analyse les menus du jeu (environ
  1 min 30, une seule fois) ; ensuite c'est quasi instantané.
- **Retirer du jeu** supprime tout ce que l'outil a écrit : le jeu redevient l'original.
- **Partager…** donne ton pack sous forme de **code** (un texte qui commence par `BT3-1-`, quelques centaines de
  caractères) : copie-le dans un message, tes amis le collent dans **Partager… → Charger le pack d'un ami**, puis
  **Appliquer au jeu**. Le code contient tout le pack, sans serveur, et aucune donnée du jeu.
- L'**empreinte** (ex. `874D-CEE7`, dans la fenêtre Partager et après « Appliquer ») résume ce que le pack change :
  pour jouer en ligne ensemble, vérifiez que vous avez tous la même.
- **Enregistrer…** (Ctrl+S) crée un petit fichier `.bt3mod.json`, qui s'ouvre avec **Ouvrir…** (Ctrl+O) : l'autre
  façon de garder ou d'envoyer un pack. Une étoile dans la barre de titre signale un pack pas encore enregistré ;
  l'outil propose de l'enregistrer avant de fermer.

## Les deux éditions du port

- **L'édition officielle** (celle de z3xox, github.com/z3xox/Tenkaichi3Decomp) : tout ce que fait l'outil marche
  hors ligne, **sauf les personnages ajoutés**. En ligne, son menu « Tenkaichi Budokai Online » refuse un jeu
  moddé.
- **L'édition étendue** (celle de BT3 Mod Studio : la même, plus deux choses) :
  - les **personnages ajoutés** (jusqu'à 57), grâce aux « paquets de personnages » que z3xox prépare ;
  - le **jeu en ligne avec des mods**, entre joueurs qui ont **exactement le même pack** (voir ci-dessous).

  Elle s'installe par-dessus le jeu comme une mise à jour (le zip ne contient aucune donnée du jeu : chacun garde
  les siennes).

## Jouer en ligne ensemble

En ligne, le jeu n'échange que les boutons pressés : chaque joueur calcule le combat chez lui. **Tous les
joueurs doivent donc appliquer exactement le même pack**, sinon le combat se désynchronise.

Avec l'édition étendue, le jeu le vérifie lui-même : à la connexion, les deux jeux comparent l'empreinte de leurs
données (mods et personnages ajoutés compris). Différentes, le match ne démarre pas et le jeu dit « version ou mods
différents ». Dans F1 > Online, « Your game data » montre cette empreinte : comparez-la entre amis.
Pour se connecter : F1 > Online, l'un héberge sur un port, l'autre rejoint son adresse (un réseau virtuel comme
Radmin VPN ou Tailscale évite d'ouvrir un port). Les codes de salon du menu en ligne demandent un service à nous,
pas encore installé.

## Pas encore possible

- Changer les fusions (elles restent celles du personnage copié).
- Mélanger des voix : une copie parle avec la voix du personnage copié.
