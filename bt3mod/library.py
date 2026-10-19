"""The library of character mods: the community's mods, imported once, kept by the tool (not in the game, not in a
pack: they are other people's work and hold game data), and used as the starting point of an added character.

A community mod is an archive (.7z, .zip) or a folder with the game's files named the community's way
(docs: memory "community mods"):
    PZS3US1\\<Group>_<k>p.pak, _<k>p_dmg.pak, _anm.pak, _eff.pak, _Voice_JP.pak, _Voice_US.pak,
            _img.cdbt (large portrait), _tag_P1.dbt / _tag_P2.dbt (member blocks)
    PZS3US2\\<Group>_<500 + line>_<JP|US>.adx (spoken lines)
<Group> is the community's name of a disc slot ("Turles_1" = Great Ape Turles: slotnames.py) when the mod was made
to replace it, or a name of its own (Android_21, Frost...). Each group with a model becomes one entry of the
library: a folder in the layout of a character package (chara_1p.pak... voice_us/NNN.adx, portrait.bin) and
info.json (its name, the mod it came from, the slot its name says, the disc character it stands on, a mark).
Files that are not a character (stages, odd files) are listed as left out."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile

from . import game as gm
from . import importer, pak, roster, slotnames

KIND_RE = re.compile(r"(.*?)_(?:(\d)p(_dmg)?|(anm|eff)|voice_(us|jp)|(img)|tag_p([12]))$", re.I)
LINE_RE = re.compile(r"(.*?)_(\d{3})_(jp|us)$", re.I)


class LibraryError(Exception):
    pass


def root():
    """%LOCALAPPDATA%\\BT3 Mod Studio\\library (BT3MS_LIBRARY: another folder, for the tests)."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.environ.get("BT3MS_LIBRARY") or os.path.join(base, "BT3 Mod Studio", "library")
    os.makedirs(d, exist_ok=True)
    return d


def pretty(name):
    """A mod's file name as people read it: "dbzl_exclusives_modpack_-_volume_1" -> "Dbzl Exclusives Modpack -
    Volume 1"."""
    words = re.sub(r"[_\s]+", " ", name).strip().split(" ")
    return " ".join(w[:1].upper() + w[1:] for w in words if w)


def safe(name, size=48):
    name = "".join(ch for ch in name if ch.isalnum() or ch in " -_()'.").strip()[:size]
    return name or "Mod"


# ---- unpacking an archive -----------------------------------------------------------------------------------------
def _check_names(names):
    for n in names:
        parts = n.replace("\\", "/").split("/")
        if n.startswith(("/", "\\")) or ".." in parts or (len(parts[0]) == 2 and parts[0][1] == ":"):
            raise LibraryError(f"l'archive contient un chemin dangereux : {n}")


def extract(src, dest):
    """The mod at `src` (a .7z, a .zip or a folder) unpacked into `dest`; returns the folder to read."""
    low = src.lower()
    if os.path.isdir(src):
        return src
    if low.endswith(".zip"):
        with zipfile.ZipFile(src) as z:
            _check_names(z.namelist())
            z.extractall(dest)
    elif low.endswith(".7z"):
        try:
            import py7zr
        except ImportError:
            raise LibraryError("les archives .7z ne peuvent pas être ouvertes (module py7zr absent)")
        with py7zr.SevenZipFile(src) as z:
            _check_names(z.getnames())
            z.extractall(dest)
    else:
        raise LibraryError("choisis un dossier, un .zip ou un .7z")
    return dest


# ---- reading the files --------------------------------------------------------------------------------------------
def scan(folder):
    """({group: {"files": {target name: path}, "kinds": set}}, notes). Target names are the package's
    (chara_1p.pak, voice_us/012.adx...)."""
    groups, notes, loose = {}, [], []
    for top, _, files in os.walk(folder):
        for f in sorted(files):
            path = os.path.join(top, f)
            stem, ext = os.path.splitext(f)
            m = KIND_RE.match(stem)
            a = LINE_RE.match(stem) if ext.lower() == ".adx" else None
            if a:
                group, num, lang = a.group(1), int(a.group(2)), a.group(3).lower()
                line = num - 500 if num >= 500 else num
                if 0 <= line < 100:
                    g = groups.setdefault(group, {"files": {}, "kinds": set()})
                    g["files"][f"voice_{lang}/{line:03d}.adx"] = path
                    g["kinds"].add("lines")
                continue
            if m and ext.lower() in (".pak", ".cdbt", ".dbt", ".unk", ".bin"):
                group = m.group(1)
                if m.group(2):
                    k = int(m.group(2))
                    target, kind = f"chara_{k}p{'_dmg' if m.group(3) else ''}.pak", "dmg" if m.group(3) else "model"
                elif m.group(4):
                    target = kind = f"chara_{m.group(4).lower()}.pak"
                elif m.group(5):
                    target = kind = f"chara_voice_{m.group(5).lower()}.pak"
                elif m.group(6):
                    target, kind = "portrait.bin", "portrait"
                else:
                    target, kind = f"member_{m.group(7)}p.bin", "member"
                g = groups.setdefault(group, {"files": {}, "kinds": set()})
                g["files"][target] = path
                g["kinds"].add(kind)
                continue
            if f.lower() in ("character.txt",) or ext.lower() in (".txt", ".afl", ".png", ".jpg", ".md", ".url"):
                continue
            loose.append(path)
    # files without the community's names (one character passed around file by file): what they are, by their
    # numbers and their contents (importer.classify), as one group named after the folder
    if loose and not any("model" in g["kinds"] for g in groups.values()):
        tmp = tempfile.mkdtemp(prefix="bt3loose_", dir=folder)  # (inside the unpacked mod: removed with it)
        for p in loose:
            shutil.copy2(p, tmp)
        found, more = importer.classify(tmp)
        notes += more
        files = {}
        models = sorted(k for k in found if k.startswith("model"))
        for i, k in enumerate(models):
            files[f"chara_{i + 1}p.pak"] = found[k][0]
            if "dmg" + k[-1] in found:
                files[f"chara_{i + 1}p_dmg.pak"] = found["dmg" + k[-1]][0]
        for k in ("anm", "eff", "voice_us", "voice_jp"):
            if k in found:
                files[f"chara_{k}.pak"] = found[k][0]
        if "portrait" in found:
            files["portrait.bin"] = found["portrait"][0]
        if files:
            slot = next((w for _, w in found.values() if w is not None), None)
            groups[os.path.basename(folder.rstrip("/\\"))] = {"files": files, "kinds": {"model"}, "slot": slot}
    else:
        notes += [f"{os.path.basename(p)} : pas un fichier de personnage, laissé de côté" for p in loose]
    for name in [n for n, g in groups.items() if "model" not in g["kinds"] and "dmg" not in g["kinds"]]:
        notes.append(f"{name} : pas de modèle de personnage (stage, image…), laissé de côté")
        del groups[name]
    return groups, notes


# ---- the disc character a mod stands on ---------------------------------------------------------------------------
_DISC = {}


def _disc_hashes(game, k):
    """{chara: set of hashes of the entries of its file k of the block (8 = animations; 0 = first costume)}."""
    key = (game.root, k)
    if key not in _DISC:
        out = {}
        for c in range(gm.CHARA_COUNT):
            try:
                ents = pak.read(game.original(gm.CHARA_FIRST + c * 10 + k))
            except Exception:
                continue
            out[c] = {hashlib.sha1(e).digest() for e in ents if e}
        _DISC[key] = out
    return _DISC[key]


def guess_base(game, files, slot=None):
    """(disc character, why) the mod stands on: the slot its name says, else the character whose animations it
    shares the most of (the computer plays it with that one's behaviour), else whose model."""
    if slot is not None:
        return slot, f"son nom est celui de {roster.name(slot)}"
    for target, k, what in (("chara_anm.pak", 8, "animations"), ("chara_1p.pak", 0, "modèle")):
        if target not in files:
            continue
        with open(files[target], "rb") as f:
            mine = {hashlib.sha1(e).digest() for e in pak.read(f.read()) if e}
        scores = sorted(((len(mine & h), c) for c, h in _disc_hashes(game, k).items()), reverse=True)
        if scores and scores[0][0]:
            c = scores[0][1]
            return c, f"ses {what} ressemblent le plus à ceux de {roster.name(c)}"
    return 0, "rien ne l'indiquait (à changer)"


# ---- the library ----------------------------------------------------------------------------------------------------
def _mark(folder):
    h = hashlib.sha256()
    for top, dirs, files in sorted(os.walk(folder)):
        dirs.sort()
        for f in sorted(files):
            if f == "info.json":
                continue
            p = os.path.join(top, f)
            h.update(os.path.relpath(p, folder).replace("\\", "/").lower().encode() + b"\0")
            with open(p, "rb") as fh:
                h.update(hashlib.sha256(fh.read()).digest())
    x = h.hexdigest().upper()
    return x[:4] + "-" + x[4:8]


def import_mod(game, src, mod_name=None):
    """Imports a community mod into the library. Returns {"mod", "entries": [info...], "notes": [...]}."""
    mod_name = safe(mod_name or os.path.splitext(os.path.basename(src.rstrip("/\\")))[0])
    tmp = tempfile.mkdtemp(prefix="bt3mod_")
    try:
        folder = extract(src, tmp)
        groups, notes = scan(folder)
        if not groups:
            raise LibraryError("aucun personnage dans ce mod (il faut au moins un modèle : un fichier …_1p.pak)"
                               + (" ; " + " ; ".join(notes[:5]) if notes else ""))
        families = {}
        for g in groups:
            families.setdefault(re.sub(r"_\d+$", "", g), []).append(g)
        out = []
        for group in sorted(groups):
            info = groups[group]
            slot = info.get("slot")
            if slot is None:
                slot = slotnames.slot_of(group)
            eid = f"{mod_name}__{safe(group, 40)}"
            dest = os.path.join(root(), eid)
            if os.path.exists(dest):
                shutil.rmtree(dest)  # (imported again: the newer files win)
            os.makedirs(dest)
            for target, path in info["files"].items():
                os.makedirs(os.path.dirname(os.path.join(dest, target)), exist_ok=True)
                shutil.copy2(path, os.path.join(dest, target))
            base, why = guess_base(game, {t: os.path.join(dest, t) for t in info["files"]}, slot)
            fam = re.sub(r"_\d+$", "", group)
            entry = {"id": eid, "mod": pretty(mod_name), "group": group,
                     "name": roster.name(slot) if slot is not None else group.replace("_", " "),
                     "slot": slot, "base": base, "why": why,
                     "family": fam if len(families.get(fam, [])) > 1 else None,
                     "costumes": len([t for t in info["files"] if re.fullmatch(r"chara_\dp\.pak", t)]),
                     "has": sorted({k for k in info["kinds"]}), "mark": _mark(dest)}
            with open(os.path.join(dest, "info.json"), "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=1)
            out.append(entry)
        return {"mod": pretty(mod_name), "entries": out, "notes": notes}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def entries():
    """Every entry of the library, by mod then name."""
    out = []
    for d in sorted(os.listdir(root())):
        e = info(d)
        if e:
            out.append(e)
    return sorted(out, key=lambda e: (e["mod"].lower(), e["group"].lower()))


def info(eid):
    try:
        with open(os.path.join(root(), eid, "info.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def path(eid, name=""):
    return os.path.join(root(), eid, name) if name else os.path.join(root(), eid)


def read(eid, name):
    with open(path(eid, name), "rb") as f:
        return f.read()


def files(eid):
    """The entry's files, as names inside a package ("chara_1p.pak", "voice_us/003.adx"...)."""
    d = path(eid)
    out = []
    for top, _, fs in os.walk(d):
        for f in fs:
            rel = os.path.relpath(os.path.join(top, f), d).replace("\\", "/")
            if rel != "info.json":
                out.append(rel)
    return sorted(out)


def remove(eid):
    if not eid or "/" in eid or "\\" in eid or eid in (".", ".."):
        raise LibraryError("pas une entrée de la bibliothèque")
    shutil.rmtree(path(eid))
