"""Access to an installed Tenkaichi3Decomp: original files, characters, and writing mods into gamedata/mods/.

The original files are never changed: a modified file is written to gamedata/mods/pzs3us1/, which the port
loads instead of the original (port/src/plat_fcache.c, Port_FileOpenHost).
"""
import json
import os
import re
import struct

from . import fields, forms, menunames, movetext, pak, transplant

CHARA_COUNT = 161
CHARA_FIRST = 1423     # pzs3us1 index of character 0's first costume (file id 0x590 - 1)
COSTUME_PAK = 252      # entry count of a costume pack
MANIFEST = "bt3modstudio_manifest.json"
MODEL_BUF_SIZE = 0xCE000  # BTL_RES_MODEL_SIZE (source/include/battle/btl_obj.h): the buffer a costume is read into
SECTOR = 0x800            # the game reads whole disc sectors
ANIM_BUF_SIZE = 0x160800  # BTL_RES_ANIM0_SIZE: the animation pack (block file +8)
EFFECT_BUF_SIZE = 0xCE800 # BTL_RES_ANIM1_SIZE: the effect pack (block file +9)
VOICE_BANK, VOICE_BANK_ALT = 0xBDA, 0xC7B        # file ids + chara: the character's sound banks
VOICE_LINES, VOICE_LINES_ALT = 0x8D4E, 0xCC32    # file ids + chara * 100 + line: the voice lines
P2_FIRST = 0xD48                                 # first file id of pzs3us2
FACE_FILE = 0x2F9                                # file id + chara: the large portrait of the select screens


class ModError(Exception):
    pass


def tool_folder():
    """The folder of the tool: next to BT3 Mod Studio.exe when it runs as a program, else the source folder."""
    import sys
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _is_gamedata(d):
    return bool(d) and os.path.isfile(os.path.join(d, "pzs3us1", "%05d.bin" % CHARA_FIRST))


def remembered_gamedata(path=None):
    """The game data folder chosen last time (bt3modstudio.json next to the tool); `path` stores a new one."""
    cfg = os.path.join(tool_folder(), "bt3modstudio.json")
    if path is not None:
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"gamedata": path}, f)
        return path
    try:
        with open(cfg, encoding="utf-8") as f:
            p = json.load(f).get("gamedata")
        return p if _is_gamedata(p) else None
    except (OSError, ValueError):
        return None


def find_gamedata(start=None):
    """Looks for the game's data folder: in `start` and its parents (or the tool's folder and its parents), then
    the folder remembered from last time. The folders searched may be the game's folder or its gamedata."""
    here = os.path.abspath(start or tool_folder())
    for d in (here, os.path.dirname(here), os.path.dirname(os.path.dirname(here))):
        for cand in (os.path.join(d, "Tenkaichi3Decomp", "gamedata"), os.path.join(d, "gamedata"), d):
            if _is_gamedata(cand):
                return cand
    return None if start else remembered_gamedata()


def costume_files(chara):
    """pzs3us1 indexes of the character's 8 costume slots (4 costumes, 4 damaged variants)."""
    base = CHARA_FIRST + chara * 10
    return [base + k for k in range(8)]


class Game:
    def __init__(self, gamedata):
        self.root = gamedata
        self.orig_dir = os.path.join(gamedata, "pzs3us1")
        self.mods_root = os.path.join(gamedata, "mods")
        self.mods_dir = os.path.join(self.mods_root, "pzs3us1")
        self._cache = {}

    # ---- original data --------------------------------------------------------------------------------------
    def original(self, index):
        with open(os.path.join(self.orig_dir, "%05d.bin" % index), "rb") as f:
            return f.read()

    def costumes(self, chara):
        """[(file index, entries)] of the costumes that exist, from the original disc data."""
        out = []
        for idx in costume_files(chara):
            data = self.original(idx)
            if struct.unpack_from("<I", data, 0)[0] == COSTUME_PAK:
                out.append((idx, pak.read(data)))
        return out

    def base_entries(self, chara):
        """Entries of the character's first costume (the first file that is one: 1 file read, not 8)."""
        if chara not in self._cache:
            for idx in costume_files(chara):
                data = self.original(idx)
                if struct.unpack_from("<I", data, 0)[0] == COSTUME_PAK:
                    self._cache[chara] = pak.read(data)
                    break
            else:
                raise IndexError(f"character {chara}: no costume file")
        return self._cache[chara]

    def roster_entries(self):
        if "roster" not in self._cache:
            self._cache["roster"] = pak.read(self.original(fields.ROSTER_FILE))
        return self._cache["roster"]

    def original_values(self, chara):
        e = self.base_entries(chara)
        out = {}
        for f in fields.FIELDS:
            if f.kind == "scale":
                out[f.key] = 100
            elif f.where == "roster":
                out[f.key] = f.read(self.roster_entries(), chara * fields.ROSTER_ROW)
            else:
                out[f.key] = f.read(e)
        return out

    def mod_entries(self, mod):
        """Entries of the first costume of a mod of the library (an added character made from it)."""
        key = ("mod", mod)
        if key not in self._cache:
            from . import library
            try:
                self._cache[key] = pak.read(library.read(mod, "chara_1p.pak"))
            except OSError:
                raise ModError(f"le mod « {mod} » n'est pas dans la bibliothèque de mods : importe-le d'abord")
        return self._cache[key]

    def source_entries(self, chara, change):
        """The costume a character starts from: its mod's (key "mod", an added character made from a mod of the
        library), else its base character's (key "base"), else its own."""
        if change.get("mod"):
            return self.mod_entries(change["mod"])
        return self.base_entries(int(change.get("base", chara)))

    def graft_conflict(self, chara, change, t):
        """None when technique graft t fits the slot, else a message saying why not."""
        from . import roster
        base = int(change.get("base", chara))
        entries = list(self.source_entries(chara, change))
        if transplant.is_skill(t):
            name = (self.move_names(int(t["from"])) + [""] * 2)[int(t["fromSlot"])].strip() or "cette attaque"
        else:
            name = self.technique_names(int(t["from"]))[int(t["fromSlot"])] or "cette attaque"
        try:
            for g in change.get("transplants", []):
                transplant.apply_to_costume(entries, self.base_entries(int(g["from"])), int(g["slot"]),
                                            int(g["fromSlot"]), skill=transplant.is_skill(g))
                if g is t:
                    break
        except transplant.IncompatibleGraft:
            return (f"« {name} » de {roster.name(int(t['from']))} ne peut pas aller sur ce personnage : elle a besoin "
                    "d'animations ou de caméras propres à son personnage, et ce personnage utilise déjà ces "
                    "emplacements pour ses propres attaques.")
        # (the sizes with every graft of the slot: they add up)
        for k, data, limit, what in self._graft_packs(base, change.get("transplants", []), change.get("mod")):
            size = (len(data) + SECTOR - 1) // SECTOR * SECTOR
            if size > limit:
                return (f"« {name} » de {roster.name(int(t['from']))} ne rentre pas sur ce personnage : avec elle, "
                        f"ses {what} prendraient {size // 1024} Ko, et le jeu leur réserve {limit // 1024} Ko. "
                        "Essaie une autre attaque, ou un autre emplacement (Blast 2 plutôt qu'Ultime par exemple).")
        return None

    def preview_entries(self, chara, change):
        """Costume 0 of a character as the pack makes it before its number changes: the base character (key
        "base") with the techniques grafted onto it (key "transplants")."""
        entries = list(self.source_entries(chara, change))
        for t in change.get("transplants", []):
            try:
                transplant.apply_to_costume(entries, self.base_entries(int(t["from"])), int(t["slot"]),
                                            int(t["fromSlot"]), skill=transplant.is_skill(t))
            except transplant.IncompatibleGraft:
                pass  # (the editor refuses such a graft when it is chosen: graft_conflict)
        return entries

    def start_values(self, chara, change):
        """The values the editor starts from: original_values of what the pack puts in the slot before its own
        number changes (the base character, its grafted techniques)."""
        e = self.preview_entries(chara, change)
        row = int(change.get("base", chara))
        out = {}
        for f in fields.FIELDS:
            if f.kind == "scale":
                out[f.key] = 100
            elif f.where == "roster":
                out[f.key] = f.read(self.roster_entries(), row * fields.ROSTER_ROW)
            else:
                out[f.key] = f.read(e)
        return out

    def start_move_names(self, chara, change, lang="en"):
        e = self.preview_entries(chara, change)
        return [n for _, n in movetext.specials(movetext.decode(e[movetext.LANGS[lang][0]]))]

    def technique_names(self, chara, lang="en"):
        """The names of a character's three techniques (Blast 2 n°1, Blast 2 n°2, Ultimate), when its move list
        has the standard order (Blast 1 x2, Blast 2 x2, Ultimate, Hyper Smash); else None for each."""
        names = self.move_names(chara, lang)
        if len(names) == 6:
            return [names[2].strip(), names[3].strip(), names[4].strip()]
        return [None, None, None]

    def move_names(self, chara, lang="en"):
        e = self.base_entries(chara)
        return [n for _, n in movetext.specials(movetext.decode(e[movetext.LANGS[lang][0]]))]

    def label(self, chara):
        """A name built from the character's moves (the game draws character names as pictures)."""
        names = [n.strip() for n in self.move_names(chara) if n.strip() != "Hyper Smash"]
        if not names:
            return "(sans attaque spéciale)"
        # special moves come as Blast 1 x2, Blast 2 x2, Ultimate: show the Ultimate, then the first Blast 2
        return names[-1] + (" · " + names[2] if len(names) >= 5 else "")

    # ---- transformations and grid forms ----------------------------------------------------------------------
    @staticmethod
    def clones(pack):
        """{original id: id of its copy} of the pack's replaced slots (the first copy of an original)."""
        out = {}
        for c, ch in sorted(pack.get("characters", {}).items(), key=lambda kv: int(kv[0])):
            if "base" in ch and int(ch["base"]) != int(c):
                out.setdefault(int(ch["base"]), int(c))
        return out

    def params(self, chara):
        """A character's original general parameters (costume entry 17)."""
        return self.base_entries(chara)[fields.ENTRY_PARAM]

    def transform_templates(self):
        if "ttpl" not in self._cache:
            self._cache["ttpl"] = forms.templates(self.params(c) for c in range(CHARA_COUNT))
        return self._cache["ttpl"]

    def transforms(self, chara, change, pack):
        """The 4 transformation slots the pack gives the character (forms.py): its own choice (key "transforms"),
        else those of the character it copies, aimed at the pack's copies of their targets."""
        base = int(change.get("base", chara))
        own = forms.read(self.source_entries(chara, change)[fields.ENTRY_PARAM])
        if change.get("transforms") is not None:
            chosen = change["transforms"]
            if len(chosen) != forms.SLOTS or any(c is not None and not 0 <= int(c["to"]) < CHARA_COUNT
                                                 for c in chosen):
                raise ModError(f"personnage {chara} : transformations invalides {chosen}")
            return forms.resolve(chosen, own, *self.transform_templates())
        return forms.remap(own, self.clones(pack)) if base != chara and not change.get("mod") else own

    def grid(self):
        """The cells of the character select grid on the disc (without the long first scan of the menus)."""
        if "grid" not in self._cache:
            c = self._cache.get("menumap") or menunames.cached(self.root, tool_folder())
            self._cache["grid"] = c[2]["grid"] if c else menunames.read_grid(self.original(menunames.GRID_FILE))
        return self._cache["grid"]

    def heads_cell(self, chara):
        return forms.cell_of(self.grid(), chara) is not None

    def grid_forms(self, chara, change, pack):
        """The forms the pack gives the grid cell this character heads (key "forms"; for a copy, by default the
        forms of the character it copies, forms.default_forms), or None when it has no cell or keeps it."""
        base = int(change.get("base", chara))
        if not change.get("forms") and base == chara:
            return None  # (before the grid: reading it may need the long first scan of the menus)
        if forms.cell_of(self.grid(), chara) is None:
            return None
        if change.get("forms"):
            f = [int(x) for x in change["forms"]]
            if f[0] != chara or len(f) > forms.MAX_FORMS or any(not 0 <= x < CHARA_COUNT for x in f):
                raise ModError(f"personnage {chara} : formes de la grille invalides {f}")
            return f
        return forms.default_forms(self.grid(), chara, base, self.params, self.clones(pack))

    # ---- writing a mod pack into the game ---------------------------------------------------------------------
    def _manifest_path(self):
        return os.path.join(self.root, "mods", MANIFEST)

    def manifest(self):
        try:
            with open(self._manifest_path(), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"files": []}

    def _save_manifest(self, m):
        os.makedirs(os.path.dirname(self._manifest_path()), exist_ok=True)
        with open(self._manifest_path(), "w", encoding="utf-8") as f:
            json.dump(m, f, indent=1)

    # ---- the files of a character ----------------------------------------------------------------------------
    def original_rel(self, rel):
        with open(os.path.join(self.root, rel), "rb") as f:
            return f.read()

    @staticmethod
    def character_files(chara):
        """Every file of the disc that belongs to one character, as paths under gamedata (file id formulas from
        source/include/battle/battle_work.h and docs/systems/files_and_assets.md; pzs3us1 index = id - 1,
        pzs3us2 index = id - 0xD48)."""
        p1 = [CHARA_FIRST + chara * 10 + k for k in range(10)]           # costumes, damaged, animations, effects
        p1 += [7 + chara * 2, 8 + chara * 2]                              # per-side data (id 8 + chara * 2 + side)
        p1 += [VOICE_BANK - 1 + chara, VOICE_BANK_ALT - 1 + chara]        # sound banks (0xBDA / 0xC7B + chara)
        p1 += [FACE_FILE - 1 + chara]                                     # large portrait (menus: 0x2F9 + chara)
        p2 = [base - P2_FIRST + chara * 100 + line for base in (VOICE_LINES, VOICE_LINES_ALT) for line in range(100)]
        return ["pzs3us1/%05d.bin" % i for i in p1] + ["pzs3us2/%05d.bin" % i for i in p2]

    def build_character(self, chara, change, pack=None):
        """Returns {path under gamedata: new file bytes} for one character's changes (modpack.py: `change`).
        With "base": the character in this slot becomes a copy of that character (every file of it), and the other
        changes apply to the copy."""
        values = change.get("fields", {})
        texts = change.get("texts", {})
        grafts = change.get("transplants", [])
        base = int(change.get("base", chara))
        if not 0 <= base < CHARA_COUNT:
            raise ModError(f"personnage {chara} : personnage de base inconnu {base}")
        for t in grafts:
            top = 1 if transplant.is_skill(t) else 2
            if not (0 <= int(t["slot"]) <= top and 0 <= int(t["fromSlot"]) <= top and 0 <= int(t["from"]) < CHARA_COUNT):
                raise ModError(f"personnage {chara} : greffe d'attaque invalide {t}")
        slots = self.transforms(chara, change, pack or {})
        new_slots = slots != forms.read(self.params(base))
        out = {}
        if base != chara:  # every file of the base character, in this character's place
            for dst, src in zip(self.character_files(chara), self.character_files(base)):
                data = self.original_rel(src)
                if data != self.original_rel(dst):
                    out[dst] = data
        first = CHARA_FIRST + chara * 10
        for sidx, entries in self.costumes(base):
            idx = first + (sidx - (CHARA_FIRST + base * 10))
            entries = list(entries)
            for t in grafts:
                try:
                    transplant.apply_to_costume(entries, self.base_entries(int(t["from"])), int(t["slot"]),
                                                int(t["fromSlot"]), skill=transplant.is_skill(t))
                except transplant.IncompatibleGraft:
                    raise ModError(self.graft_conflict(chara, change, t))
            for key, value in fields.ordered(values):
                f = fields.BY_KEY.get(key)
                if f is None:
                    raise ModError(f"paramètre inconnu : {key}")
                if f.where == "roster":
                    continue  # written once for everyone by build_roster
                fields.write_value(entries, f, value)
            if new_slots:
                entries[fields.ENTRY_PARAM] = forms.write(entries[fields.ENTRY_PARAM], slots)
            for lang, renames in texts.items():
                if lang not in movetext.LANGS:
                    raise ModError(f"langue inconnue : {lang}")
                ent = movetext.LANGS[lang][0]
                text = movetext.decode(entries[ent])
                for i, name in renames.items():
                    text = movetext.rename(text, int(i), name)
                entries[ent] = movetext.encode(text)
            data = pak.write(entries)
            sectors = (len(data) + SECTOR - 1) // SECTOR * SECTOR
            if sectors > MODEL_BUF_SIZE:
                raise ModError(f"personnage {chara} : le costume pzs3us1/{idx:05d} dépasse de "
                               f"{sectors - MODEL_BUF_SIZE} octets la place que le jeu lui réserve "
                               "(raccourcis les nouveaux noms)")
            rel = "pzs3us1/%05d.bin" % idx
            if data != self.original_rel(rel):
                out[rel] = data
            else:
                out.pop(rel, None)
        if grafts:
            for k, data, limit, what in self._graft_packs(base, grafts):
                if (len(data) + SECTOR - 1) // SECTOR * SECTOR > limit:
                    raise ModError(f"personnage {chara} : le pack d'{what} greffé est trop gros pour le jeu "
                                   f"({len(data)} octets, {limit} au plus)")
                out["pzs3us1/%05d.bin" % (first + k)] = data
        return out

    def _graft_packs(self, base, grafts, mod=None):
        """[(block file +k, data, the game's buffer size, what)] of the animation and effect packs of character
        `base` (or of mod `mod` of the library, where it has them) with the techniques grafted onto it."""
        from . import library
        out = []
        for k, step, limit, what in ((8, transplant.apply_to_anims, ANIM_BUF_SIZE, "animations"),
                                     (9, transplant.apply_to_effects, EFFECT_BUF_SIZE, "effets")):
            own = f"chara_{'anm' if k == 8 else 'eff'}.pak"
            if mod and os.path.exists(library.path(mod, own)):
                entries = pak.read(library.read(mod, own))
                limit = max(limit, 1443840 if k == 8 else 845824)  # (a package's own buffers: the extended edition's)
            else:
                entries = pak.read(self.original(CHARA_FIRST + base * 10 + k))
            for t in grafts:
                src = pak.read(self.original(CHARA_FIRST + int(t["from"]) * 10 + k))
                step(entries, src, int(t["slot"]), int(t["fromSlot"]), skill=transplant.is_skill(t))
            out.append((k, pak.write(entries), limit, what))
        return out

    # ---- added characters (the extended edition of the port: character packages) -------------------------------
    def characters_dir(self):
        """The folder the extended edition reads character packages from: `characters` next to the game."""
        return os.path.join(os.path.dirname(os.path.abspath(self.root)), "characters")

    def edition(self):
        """Which port is installed next to the data: "etendu" (BT3 Mod Studio's edition: added characters, online
        with the same mods), "officielle", or None when no program is found."""
        if "edition" not in self._cache:
            found = None
            for exe in ("Tenkaichi3Decomp.exe", "bt3.exe", "Tenkaichi3Decomp", "bt3"):
                path = os.path.join(os.path.dirname(os.path.abspath(self.root)), exe)
                try:
                    with open(path, "rb") as f:
                        found = "etendu" if b"plays games with the same data only" in f.read() else "officielle"
                    break
                except OSError:
                    continue
            self._cache["edition"] = found
        return self._cache["edition"]

    @staticmethod
    def added_folder(n, entry):
        """The package folder of added character n (0-based) of a pack. The game reads the folders in the order of
        their names, which gives the added characters their ids: two players with the same pack get the same."""
        name = "".join(ch for ch in str(entry.get("name", "")) if ch.isalnum() or ch in " -_()'.")[:40].strip()
        return f"BT3MS {n + 1:02d} {name or 'Personnage'}"

    def build_added(self, entry, pack=None):
        """{file name: bytes} of the package folder of an added character (pack key "added"): its costumes made
        from its base character's with the entry's changes (values, move names, grafted attacks, transformations),
        the animations and effects when attacks were grafted (else the base's are used), and character.txt (name,
        form, base, health, ki, blast stocks). Its pictures and voice are its base's (the game's rule)."""
        from . import roster
        base = int(entry.get("base", -1))
        if not 0 <= base < CHARA_COUNT:
            raise ModError(f"personnage ajouté « {entry.get('name', '')} » : personnage de base inconnu {base}")
        change = {k: v for k, v in entry.items() if k not in ("base", "name", "form")}
        first, stem = CHARA_FIRST + base * 10, "chara"
        if entry.get("mod"):  # (made from a mod of the library: its files, changed where the pack says)
            files, built = self._build_from_mod(entry["mod"], base, change), {}
        else:  # (made from a disc character: its costumes, changed where the pack says)
            files, built = {}, self.build_character(base, change, None)
            for idx, _ in self.costumes(base):
                k = idx - first
                rel = "pzs3us1/%05d.bin" % idx
                name = f"{stem}_{k + 1}p.pak" if k < 4 else f"{stem}_{k - 3}p_dmg.pak"
                files[name] = built.get(rel) or self.original(idx)
        for k, suffix in ((8, "_anm.pak"), (9, "_eff.pak")):
            rel = "pzs3us1/%05d.bin" % (first + k)
            if rel in built:
                files[stem + suffix] = built[rel]
        lines = ["# Fait avec BT3 Mod Studio" + (f" (pack « {pack.get('name', '')} »)" if pack else ""),
                 "format=1", f"name={entry.get('name') or roster.name(base)}", f"base={base}"]
        if "form" in entry:
            lines.append(f"form={entry['form']}")
        if pack and pack.get("author"):
            lines.append(f"author={pack['author']}")
        values = entry.get("fields", {})
        for key, out, lo, hi in (("roster.health", "health", 10000, 150000), ("roster.kiStart", "ki", 0, 100000),
                                 ("roster.stocks", "blast", 0, 7)):
            if key in values:
                lines.append(f"{out}={max(lo, min(hi, int(values[key])))}")
        files["character.txt"] = ("\n".join(lines) + "\n").encode("utf-8")
        return files

    def _build_from_mod(self, mod, base, change):
        """{file name: bytes} of an added character made from mod `mod` of the library: its files, the costumes
        with the pack's changes (grafted attacks, values, transformations, move names) where there are any, and
        the animations and effects with the grafted attacks' (the mod's own, else the base character's)."""
        from . import library
        if library.info(mod) is None:
            raise ModError(f"le mod « {mod} » n'est pas dans la bibliothèque de mods : importe-le d'abord")
        grafts = change.get("transplants", [])
        own = forms.read(self.mod_entries(mod)[fields.ENTRY_PARAM])
        slots = self.transforms(base, change, {})
        files = {}
        for name in library.files(mod):
            data = library.read(mod, name)
            if re.fullmatch(r"chara_\dp(_dmg)?\.pak", name):
                entries = pak.read(data)
                changed = False
                for t in grafts:
                    try:
                        transplant.apply_to_costume(entries, self.base_entries(int(t["from"])), int(t["slot"]),
                                                    int(t["fromSlot"]), skill=transplant.is_skill(t))
                    except transplant.IncompatibleGraft:
                        raise ModError(self.graft_conflict(base, change, t))
                    changed = True
                for key, value in fields.ordered(change.get("fields", {})):
                    f = fields.BY_KEY.get(key)
                    if f is None:
                        raise ModError(f"paramètre inconnu : {key}")
                    if f.where == "roster":
                        continue  # (character.txt: health, ki, blast stocks)
                    fields.write_value(entries, f, value)
                    changed = True
                if slots != own:
                    entries[fields.ENTRY_PARAM] = forms.write(entries[fields.ENTRY_PARAM], slots)
                    changed = True
                for lang, renames in change.get("texts", {}).items():
                    if lang not in movetext.LANGS or not renames:
                        continue
                    ent = movetext.LANGS[lang][0]
                    text = movetext.decode(entries[ent])
                    for i, newname in renames.items():
                        text = movetext.rename(text, int(i), newname)
                    entries[ent] = movetext.encode(text)
                    changed = True
                files[name] = pak.write(entries) if changed else data  # (untouched: the mod's bytes as they are)
            else:
                files[name] = data
        if grafts:
            for k, data, limit, what in self._graft_packs(base, grafts, mod):
                if (len(data) + SECTOR - 1) // SECTOR * SECTOR > limit:
                    raise ModError(f"le pack d'{what} greffé est trop gros pour le jeu ({len(data)} octets, {limit} au "
                                   "plus)")
                files["chara_anm.pak" if k == 8 else "chara_eff.pak"] = data
        return files

    def build_roster(self, pack):
        """The shared character table with every character's roster fields (and the rows of copied characters),
        or None when the pack changes none. Patched in place (same size), so nothing else in the file moves."""
        rows = [(int(c), int(ch["base"])) for c, ch in pack.get("characters", {}).items()
                if "base" in ch and int(ch["base"]) != int(c)]
        changes = [(int(c), fields.BY_KEY[k], v) for c, ch in pack.get("characters", {}).items()
                   for k, v in ch.get("fields", {}).items() if k in fields.BY_KEY and fields.BY_KEY[k].where == "roster"]
        if not changes and not rows:
            return None
        data = bytearray(self.original(fields.ROSTER_FILE))
        start = struct.unpack_from("<I", data, 4 + 4 * fields.ROSTER_ENTRY)[0]
        R = fields.ROSTER_ROW
        orig = bytes(data)
        for chara, base in rows:
            data[start + chara * R:start + (chara + 1) * R] = orig[start + base * R:start + (base + 1) * R]
        for chara, f, v in changes:
            struct.pack_into(f.fmt, data, start + chara * R + f.offset, int(f.clamp(v)))
        return bytes(data)

    def menu_name(self, chara, form=False):
        """The name (or form name) the menus give a character on the original disc."""
        return self.menu_map()[2]["forms" if form else "names"][chara]

    def menu_map(self):
        if "menumap" not in self._cache:
            self._cache["menumap"] = menunames.menu_map(self.root, self.original, tool_folder())
        return self._cache["menumap"]

    def build_menus(self, pack):
        """The menu archives with the names (and form names) the pack gives characters (keys menuName, menuForm)."""
        chars = pack.get("characters", {})
        names = {int(c): ch["menuName"] for c, ch in chars.items() if ch.get("menuName")}
        form_names = {int(c): ch["menuForm"] for c, ch in chars.items() if "menuForm" in ch}
        # a slot replaced by a copy of another character takes its grid portrait, and its names unless given
        chips, cells = {}, {}
        for c, ch in chars.items():
            f = self.grid_forms(int(c), ch, pack)
            if f is not None and f != forms.cell_forms(forms.cell_of(self.grid(), int(c))):
                cells[int(c)] = f
            if "base" in ch and int(ch["base"]) != int(c):
                b = int(ch["base"])
                chips[int(c)] = b
                if not ch.get("menuName"):
                    names[int(c)] = self.menu_name(b)
                if "menuForm" not in ch:
                    form_names[int(c)] = self.menu_name(b, form=True)
        if not names and not form_names and not chips and not cells:
            return {}
        wanted = {"chips"} if chips else set()
        wanted |= {"names"} if names else set()
        wanted |= {"forms"} if form_names else set()
        wanted |= {"grid"} if cells else set()
        out = {}
        where_map, tables, _ = self.menu_map()
        for idx, where in sorted(where_map.items()):
            where = [w for w in where if w[1] in wanted]
            if not where:
                continue
            try:
                data = menunames.apply(self.original(idx), where, names, form_names, chips, tables.get(idx), cells)
            except ValueError as e:
                raise ModError(str(e))
            if data != self.original(idx):
                out["pzs3us1/%05d.bin" % idx] = data
        return out

    def apply(self, pack, added=True):
        """Writes the pack into gamedata/mods/ (and, with `added`, its added characters as packages: the extended
        edition). Removes what an earlier apply wrote first. Returns the file count."""
        built = {}
        for chara, change in pack.get("characters", {}).items():
            built.update(self.build_character(int(chara), change, pack))
        roster = self.build_roster(pack)
        if roster is not None:
            built["pzs3us1/%05d.bin" % fields.ROSTER_FILE] = roster
        built.update(self.build_menus(pack))
        packages = {self.added_folder(n, e): self.build_added(e, pack)
                    for n, e in enumerate(pack.get("added", []) if added else [])}
        old_pkgs = set(self.manifest().get("packages", []))
        for folder in packages:
            pass  # ("BT3MS NN ..." folders are always this tool's: one left by an apply that stopped is replaced)
        old = set(self._manifest_paths())
        for rel in built:
            if os.path.exists(os.path.join(self.mods_root, rel)) and rel not in old:
                raise ModError(f"mods/{rel} existe déjà et ne vient pas de cet outil : retire-le à la main d'abord")
        self.remove()
        written = []
        for rel, data in sorted(built.items()):
            path = os.path.join(self.mods_root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            written.append(rel)
        for folder, files in sorted(packages.items()):
            d = os.path.join(self.characters_dir(), folder)
            if os.path.isdir(d):
                import shutil
                shutil.rmtree(d)  # (no file of an older version of it left behind)
            os.makedirs(d, exist_ok=True)
            for name, data in files.items():
                os.makedirs(os.path.dirname(os.path.join(d, name)), exist_ok=True)  # (voice_us/, voice_jp/)
                with open(os.path.join(d, name), "wb") as f:
                    f.write(data)
        self._save_manifest({"files": written, "packages": sorted(packages), "pack": pack.get("name", "")})
        return len(written) + sum(len(f) for f in packages.values())

    def _manifest_paths(self):
        # (an older manifest names pzs3us1 files without their folder)
        return [n if "/" in n else "pzs3us1/" + n for n in self.manifest().get("files", [])]

    def remove(self):
        """Deletes the files this tool wrote. Returns how many."""
        import shutil
        n = 0
        for rel in self._manifest_paths():
            p = os.path.join(self.mods_root, rel)
            if os.path.exists(p):
                os.remove(p)
                n += 1
        for folder in self.manifest().get("packages", []):  # (only the folders this tool wrote, by their names)
            d = os.path.join(self.characters_dir(), folder)
            if folder.startswith("BT3MS ") and os.path.isdir(d):
                n += len(os.listdir(d))
                shutil.rmtree(d, ignore_errors=True)
        self._save_manifest({"files": []})
        return n
