# BT3 Mod Studio

Outil pour modifier les personnages de **Dragon Ball Z Budokai Tenkaichi 3** (USA, SLUS-21678) joué avec le port PC
[Tenkaichi3Decomp](https://github.com/z3xox/Tenkaichi3Decomp) : stats, attaques reprises d'autres personnages,
personnages copiés à la place d'un autre, transformations, formes de la grille de sélection, noms dans les menus.

**Nouveau ? Commence par le [GUIDE.md](GUIDE.md)** : installer le jeu (édition officielle ou étendue), l'outil, et
jouer en ligne ensemble avec les mêmes mods. **Mode d'emploi détaillé de la fenêtre : [LISEZMOI.md](LISEZMOI.md).**

L'édition étendue du port (personnages ajoutés, jeu en ligne avec des mods identiques) :
[Gooodak/bt3-port-etendu](https://github.com/Gooodak/bt3-port-etendu).

Le dépôt ne contient aucune donnée du jeu : l'outil lit celles de l'installation de chacun, et les packs
(`.bt3mod.json`) ne listent que des changements.

## Organisation

| Dossier / fichier | Rôle |
|---|---|
| `studio.py`, `studio_ui.py` | la fenêtre (tkinter) |
| `bt3mod/` | le moteur : lecture des fichiers du jeu, écriture des mods dans `gamedata/mods/` |
| `tools/kit.py`, `tools/kit_selftest.py` | banc de test : un exe du port compilé avec un kit de pilotage (combats, entrées, mesures) |
| `tools/ui_check.py`, `tools/ui_shot.py`, `tools/ui_speed.py` | tests de la fenêtre (utilisation, captures, vitesse) |
| `testkit-src/` | les sources du kit de test, à appliquer sur une copie du port (WSL) |
| `tools/build_exe.py` | fabrique `BT3 Mod Studio.exe` et son dossier `runtime` |

## Développer

Python 3.10 (Windows) avec numpy ; PyInstaller pour l'exe.

```
py studio.py                      # lancer la fenêtre depuis le code
py -I tools/kit_selftest.py       # tests du moteur dans le jeu de test (~1 min 30)
py -I tools/ui_check.py           # test de la fenêtre (~30 s)
py -I tools/build_exe.py          # fabriquer l'exe
```
