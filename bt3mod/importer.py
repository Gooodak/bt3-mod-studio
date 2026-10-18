"""Character mods of the community, put into the game as character packages (the extended edition's `characters`
folder, docs/port/character_packages.md of the port).

A mod comes either as a package already (a folder with character.txt, or files named *_1p.pak, *_anm.pak...) or as
the game's files passed around one by one ("Vegeta(1733).unk", "model.pak"...): the number in a name is the file's
place in the game's first archive (counted from 0, as the community's tools count), which says what the file is and
whose; where there is no number, the contents say (a model is a pack of 252 entries, animations 440, effects 6).
Nothing here comes from another tool: the file numbers are the game's own (game.py)."""
import os
import re
import shutil
import struct
import zipfile

from . import game as gm

MAX_SIZE = {"model": 1572864, "dmg": 1572864, "anm": 1443840, "eff": 845824, "voice_us": 591872, "voice_jp": 591872,
            "portrait": 92160}   # the largest file the extended edition takes of each kind (character_packages.md)
OURS = "BT3MS "                  # the folders packs write (game.added_folder): not imported mods


class ImportError_(Exception):
    pass


def pack_count(data):
    """The number of entries of a pack (u32 count, offsets), 0 when the data is not one."""
    if len(data) < 8:
        return 0
    n = struct.unpack_from("<I", data, 0)[0]
    if not 0 < n < 4096 or len(data) < 4 * (n + 2):
        return 0
    offs = struct.unpack_from("<%dI" % (n + 1), data, 4)
    return n if all(o <= len(data) for o in offs) else 0


def kind_of_number(index):
    """(kind, character) a file's number names (its place in the first archive), or (None, None)."""
    first = gm.CHARA_FIRST
    if first <= index < first + gm.CHARA_COUNT * 10:
        who, k = divmod(index - first, 10)
        return ("anm" if k == 8 else "eff" if k == 9 else f"dmg{k - 4}" if k >= 4 else f"model{k}"), who
    for base, kind in ((gm.VOICE_BANK - 1, "voice_jp"), (gm.VOICE_BANK_ALT - 1, "voice_us"),
                       (gm.FACE_FILE - 1, "portrait")):
        if base <= index < base + gm.CHARA_COUNT:
            return kind, index - base
    return None, None


def is_package(folder):
    names = [n.lower() for n in os.listdir(folder)]
    return "character.txt" in names or any(re.search(r"_1p\.pak$", n) for n in names)


def classify(folder):
    """{kind: (path, character named by its number or None)} of the loose files of a mod, and notes on what was
    left out. kinds: model0..3, dmg0..3, anm, eff, voice_us, voice_jp, portrait."""
    found, notes = {}, []
    paths = sorted(os.path.join(top, f) for top, _, files in os.walk(folder) for f in files)
    for path in paths:
        name = os.path.basename(path)
        stem = os.path.splitext(name)[0].lower()
        with open(path, "rb") as f:
            data = f.read()
        count = pack_count(data)
        kind = who = None
        named = re.search(r"_([1-4])p(_dmg)?$", stem)
        if named:
            kind = ("dmg" if named.group(2) else "model") + str(int(named.group(1)) - 1)
        else:
            kind = next((k for k in ("anm", "eff", "voice_us", "voice_jp") if stem.endswith("_" + k)), None)
        if kind is None:
            numbers = re.findall(r"\d{2,5}", stem)
            if numbers:
                kind, who = kind_of_number(int(numbers[-1]))
        by_count = {252: "model", 440: "anm", 6: "eff", 3: "voice"}.get(count)
        if kind is None or (by_count and kind != "portrait" and not kind.startswith(by_count[:3])
                            and not (by_count == "model" and kind.startswith("dmg"))):
            if by_count is None:
                notes.append(f"{name} : pas reconnu, laissé de côté")
                continue
            kind, who = {"model": "model0", "voice": "voice_us"}.get(by_count, by_count), None
        while kind in found and kind[:-1] in ("model", "dmg") and int(kind[-1]) < 3:
            kind = kind[:-1] + str(int(kind[-1]) + 1)  # (a second model: the next costume)
        if kind in found:
            notes.append(f"{name} : un deuxième fichier pour {kind}, laissé de côté")
            continue
        found[kind] = (path, who)
    return found, notes


def guess_base(game, found):
    """The disc character the mod stands on: the one its files' numbers name, else the one whose model shares the
    most entries with the mod's, else 0. Returns (id, why)."""
    for kind in sorted(found):
        if found[kind][1] is not None:
            return found[kind][1], "la place que le numéro de ses fichiers indique"
    models = sorted(k for k in found if k.startswith(("model", "dmg")))
    if models:
        from . import pak
        with open(found[models[0]][0], "rb") as f:
            mine = pak.read(f.read())
        best = (0, 0)
        for c in range(gm.CHARA_COUNT):
            try:
                other = game.base_entries(c)
            except Exception:
                continue
            if len(other) == len(mine):
                same = sum(1 for a, b in zip(mine, other) if a and a == b)
                best = max(best, (same, c))
        if best[0]:
            return best[1], "le personnage du jeu dont le modèle lui ressemble le plus"
    return 0, "rien ne l'indiquait (Goku, à changer)"


def safe_name(name):
    name = "".join(ch for ch in name if ch.isalnum() or ch in " -_()'.").strip()[:60]
    return name or "Mod"


def import_mod(game, src, name=None, base=None):
    """Puts the mod at `src` (a folder or a .zip) into the game's characters folder. Returns a report:
    {"folder", "name", "base", "why", "files": [...], "notes": [...]}."""
    import tempfile
    tmp = None
    try:
        if os.path.isfile(src) and src.lower().endswith(".zip"):
            tmp = tempfile.mkdtemp(prefix="bt3import_")
            with zipfile.ZipFile(src) as z:
                for member in z.namelist():  # (no path that leads out of the folder)
                    if member.startswith(("/", "\\")) or ".." in member.replace("\\", "/").split("/"):
                        raise ImportError_(f"le zip contient un chemin dangereux : {member}")
                z.extractall(tmp)
            entries = [os.path.join(tmp, e) for e in os.listdir(tmp)]
            src = entries[0] if len(entries) == 1 and os.path.isdir(entries[0]) else tmp
        if not os.path.isdir(src):
            raise ImportError_("choisis un dossier ou un fichier .zip")
        name = safe_name(name or os.path.splitext(os.path.basename(src.rstrip("/\\")))[0])
        if name.startswith(OURS):
            name = name[len(OURS):] or "Mod"
        dest = os.path.join(game.characters_dir(), name)
        if os.path.exists(dest):
            raise ImportError_(f"un mod « {name} » est déjà installé : retire-le d'abord, ou donne un autre nom")
        if is_package(src):
            shutil.copytree(src, dest)
            return {"folder": name, "name": name, "base": None, "why": "paquet déjà prêt, copié tel quel",
                    "files": sorted(os.listdir(dest)), "notes": []}
        found, notes = classify(src)
        models = sorted(k for k in found if k.startswith("model"))
        damaged = sorted(k for k in found if k.startswith("dmg"))
        if not models and damaged:
            models, damaged = damaged, []
        if not models:
            raise ImportError_("aucun modèle de personnage parmi ces fichiers (un modèle est un pack de 252 "
                               "entrées)" + (" ; " + " ; ".join(notes) if notes else ""))
        plan = [(k, f"chara_{i + 1}p.pak") for i, k in enumerate(models)]
        plan += [(k, f"chara_{models.index('model' + k[-1]) + 1}p_dmg.pak") for k in damaged
                 if "model" + k[-1] in models]
        plan += [(k, f"chara_{k}.pak") for k in ("anm", "eff", "voice_us", "voice_jp") if k in found]
        if "portrait" in found:
            plan.append(("portrait", "portrait.bin"))
        if base is None:
            base, why = guess_base(game, found)
        else:
            why = "choisi"
        os.makedirs(dest)
        files = []
        for kind, target in plan:
            with open(found[kind][0], "rb") as f:
                data = f.read()
            if kind == "portrait":
                data = data.rstrip(b"\0")
            limit = MAX_SIZE.get(kind.rstrip("0123"), None)
            if limit and (len(data) + 2047) // 2048 * 2048 > limit:
                notes.append(f"{os.path.basename(found[kind][0])} : trop gros pour le jeu ({len(data)} octets), "
                             "le jeu prendra celui du personnage de base")
            with open(os.path.join(dest, target), "wb") as f:
                f.write(data)
            files.append(target)
        with open(os.path.join(dest, "character.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# Importé avec BT3 Mod Studio\nformat=1\nname={name}\nbase={base}\n")
        files.append("character.txt")
        return {"folder": name, "name": name, "base": base, "why": why, "files": files, "notes": notes}
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def installed(game):
    """The character packages in the game's characters folder: [{"folder", "name", "base", "ours", "size"}]."""
    d = game.characters_dir()
    out = []
    if not os.path.isdir(d):
        return out
    for folder in sorted(os.listdir(d), key=str.lower):
        path = os.path.join(d, folder)
        if not os.path.isdir(path) or folder.startswith("."):
            continue
        info = {"folder": folder, "name": folder, "base": None, "ours": folder.startswith(OURS), "size": 0}
        for top, _, files in os.walk(path):
            info["size"] += sum(os.path.getsize(os.path.join(top, f)) for f in files)
        try:
            with open(os.path.join(path, "character.txt"), encoding="utf-8-sig", errors="replace") as f:
                for line in f:
                    key, eq, value = line.partition("=")
                    if eq and key.strip().lower() in ("name", "base", "replaces"):
                        info["replaces" if key.strip().lower() == "replaces" else key.strip().lower()] = value.strip()
        except OSError:
            pass
        out.append(info)
    return out


def remove(game, folder):
    """Takes an imported mod out of the game (only a folder of the characters folder, never one a pack wrote)."""
    if folder.startswith(OURS) or "/" in folder or "\\" in folder or folder in ("", ".", ".."):
        raise ImportError_("ce dossier n'est pas un mod importé")
    shutil.rmtree(os.path.join(game.characters_dir(), folder))


def mark(game):
    """A short mark of the installed mods' files (what the game also compares online): "XXXX-XXXX", or "" when none.
    Two friends with the same mark have the same mods installed."""
    import hashlib
    h = hashlib.sha256()
    pkgs = installed(game)
    if not pkgs:
        return ""
    for p in pkgs:
        h.update(p["folder"].lower().encode("utf-8") + b"\0")
        root = os.path.join(game.characters_dir(), p["folder"])
        for top, dirs, files in sorted(os.walk(root)):
            dirs.sort()
            for f in sorted(files, key=str.lower):
                h.update(os.path.relpath(os.path.join(top, f), root).lower().encode("utf-8") + b"\0")
                with open(os.path.join(top, f), "rb") as fh:
                    h.update(hashlib.sha256(fh.read()).digest())
    x = h.hexdigest().upper()
    return x[:4] + "-" + x[4:8]
