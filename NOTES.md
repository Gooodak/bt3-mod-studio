# Notes du projet

Ce qui est important à savoir pour continuer le projet : décisions prises, règles à respecter, procédures.
À tenir à jour à chaque étape (le mode d'emploi des joueurs est dans GUIDE.md et LISEZMOI.md).

## Les deux éditions

- **Officielle** = le port de z3xox tel quel ([z3xox/Tenkaichi3Decomp](https://github.com/z3xox/Tenkaichi3Decomp)).
  Nos packs y marchent hors ligne (fichiers dans `gamedata/mods`). Son menu en ligne refuse un jeu moddé
  (« only between two unmodded games »), depuis la 0.1.35.
- **Étendue** = notre version du port : [Gooodak/bt3-port-etendu](https://github.com/Gooodak/bt3-port-etendu), branche
  `etendu` = la dernière version de z3xox + sa branche `char-packages` (personnages ajoutés, pas encore publiée par
  lui) + nos changements :
  - en ligne entre jeux qui ont **les mêmes données** : l'empreinte des données (mods compris) et celle des paquets
    de personnages entrent dans le numéro de version comparé à la connexion (`port/src/gs/net.c`, `net_ver`) ;
  - les paquets de personnages restent actifs en ligne (`port/src/plat_charas.c`, `pkg_hidden`, `PortCharas_Hash`) ;
  - pas de service de mise en relation par défaut (celui de z3xox est réservé à ses versions officielles, il ne
    faut ni l'utiliser ni contourner sa clé) : on joue par adresse (F1 > Online), ou plus tard avec notre propre
    service Cloudflare (`BT3_MATCH_URL`, `port/matchmaking/README.md`, demande un compte Cloudflare) ;
  - les mises à jour annoncées par le jeu viennent de notre dépôt (`PORT_UPDATE_REPO`).
- **Un seul outil** pour les deux : il détecte l'édition installée (`game.edition()`, d'après une phrase de notre exe).
  Seuls les personnages ajoutés et les mods importés demandent l'étendue ; l'outil prévient sinon.

## Licences (important)

- Le code du port est sous **AGPL-3.0** depuis le 14/10/2026 (avant : MIT). Donner notre édition à quelqu'un
  oblige à lui proposer **son code source** : donner l'accès au dépôt `bt3-port-etendu` suffit (ou le rendre public).
- **Ne pas copier de code du port dans BT3 Mod Studio** (l'outil deviendrait AGPL) : par exemple l'importateur de
  mods est le nôtre (`bt3mod/importer.py`), pas `import_chara.py` de z3xox.
- **Aucune donnée du jeu** dans ce qui se partage : ni dans les dépôts, ni dans les packs, ni dans les codes, ni dans
  les zips. Les caches de l'outil sont dans `%LOCALAPPDATA%\BT3 Mod Studio`. Les paquets de personnages faits à partir
  du jeu (et les mods de la communauté) restent sur chaque PC.

## Mettre à jour l'édition étendue quand z3xox publie

`py -I tools/update_port.py` (`--check` pour seulement regarder, `--publish` pour publier la version sur GitHub) :
récupère son code, fusionne dans `etendu`, compile le jeu de test, lance les tests (en ligne, moteur, fenêtre,
import), fait le zip dans `D:\Tenkaichi3Decomp-windows-x64\releases`, pousse la branche. Il s'arrête au premier
problème (conflit de fusion, test qui échoue) sans rien pousser ; le journal est `releases\update_port.log`.
Tags de nos versions : `v0.1.NN-etendu.K` (le jeu ne lit que `v0.1.NN` pour annoncer une mise à jour).
En ligne, tous les joueurs doivent avoir la même version (le jeu le vérifie).

## Jeu en ligne entre amis

- Même pack (même code `BT3-1-…`, même empreinte dans « Partager… »), mêmes mods de personnages importés (même
  empreinte dans « Mods de personnages… »), même version de l'édition étendue.
- Connexion : F1 > Online, l'un héberge sur un port, l'autre rejoint son adresse ; un VPN (Radmin VPN, Tailscale)
  évite d'ouvrir un port.

## Tests (ne jamais utiliser le jeu du joueur)

Tout se fait sur la copie `D:\Tenkaichi3Decomp-windows-x64\testkit` (données en liens physiques, son propre dossier
`mods`, son propre `characters`). Le jeu de test s'ouvre derrière les autres fenêtres ; les tests en ligne sont sans
fenêtre. Toujours fermer le jeu de test à la fin.

| Commande | Ce qu'elle vérifie | Durée |
|---|---|---|
| `py -I tools/kit_selftest.py` | le moteur des mods en combat (dégâts, greffes, copies, transformations) | ~1 min 30 |
| `py -I tools/ui_check.py` | la fenêtre utilisée comme par une personne, puis le pack en combat | ~2 min |
| `py -I tools/net_check.py` | en ligne : mêmes mods acceptés, différents refusés, combat identique sur les deux jeux | ~5 min |
| `py -I tools/import_check.py` | l'import d'un mod de la communauté, puis un combat avec | ~1 min |

À savoir : le jeu ne lit le dossier `characters` qu'au démarrage (appliquer, puis lancer). Le jeu de test se compile
dans WSL : `testkit-src/rebuild_etendu.sh` (jeu de test), `testkit-src/release_etendu.sh` (zip à distribuer).

## Façon de travailler

- Les tests et les commits peuvent être confiés à un agent moins cher (Haiku), en arrière-plan.
- La création de personnages (modèles 3D, attaques) sera un sous-projet à part, dans sa propre conversation.
- Modèles 3D : aucun outil public connu ne convertit un modèle Blender vers le format du jeu ; les mods de la
  communauté arrivent déjà au format du jeu (`.unk` / `.pak`) et s'importent avec « Mods de personnages… ».

## À faire / en attente

- Pages « Releases » des deux dépôts (zips prêts) et accès des amis (dépôts privés : les ajouter, ou rendre public).
- Installer l'édition étendue sur le jeu du joueur (avec une copie de l'exe officiel) : attend son accord.
- Notre service de mise en relation (codes de salon) : attend un compte Cloudflare.
- Changer le personnage de base d'un mod importé depuis la fenêtre (aujourd'hui : deviné, écrit dans character.txt).
