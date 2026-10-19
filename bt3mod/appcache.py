"""What the window needs at start-up, made once from the player's own game files and kept for the next starts in
%LOCALAPPDATA%\\BT3 Mod Studio (not next to the tool: it holds pictures of the game, it is not meant to be shared):
  - cache.json: each character's special moves (to search by attack name; else 161 costume files to read) and the
    character select grid;
  - chips_<size>.png: the grid chips of the 161 characters side by side in one picture (one file to read).
The large pictures of the select screen are decoded when a character is shown (one small file each).
"""
import json
import os
import struct

from . import images, menunames, movetext, pak

CHARA_COUNT = 161
CHARA_FIRST = 1423
CHIPS_FILE = 476        # a menu archive that is one packed file holding the grid chips (the quickest to read)
COLS = 16               # chips per row of the chips picture
VERSION = 1


def cache_dir(game):
    """The cache folder of one game folder (two installs of the game do not share it)."""
    import hashlib
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    tag = hashlib.md5(os.path.normcase(os.path.abspath(game.root)).encode("utf-8")).hexdigest()[:10]
    d = os.path.join(base, "BT3 Mod Studio", tag)
    os.makedirs(d, exist_ok=True)
    return d


def _settings_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "BT3 Mod Studio", "settings.json")


def settings():
    """The person's own settings of the window (text size...): {} the first time."""
    try:
        with open(_settings_path(), encoding="utf-8") as f:
            s = json.load(f)
        return s if isinstance(s, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(**values):
    s = settings()
    s.update(values)
    try:
        os.makedirs(os.path.dirname(_settings_path()), exist_ok=True)
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(s, f)
    except OSError:
        pass


def _key(game):
    """What the cache was made from: the game folder and the sizes of the files it reads first."""
    sizes = []
    for i in (CHARA_FIRST, CHIPS_FILE, menunames.GRID_FILE):
        try:
            sizes.append(os.path.getsize(os.path.join(game.orig_dir, "%05d.bin" % i)))
        except OSError:
            sizes.append(-1)
    return {"version": VERSION, "root": os.path.abspath(game.root), "sizes": sizes}


def load(game):
    """The cached {"moves": [[names] x 161], "grid": cells} of this game, or None."""
    try:
        with open(os.path.join(cache_dir(game), "cache.json"), encoding="utf-8") as f:
            c = json.load(f)
        if c.get("key") == _key(game):
            return c
    except (OSError, ValueError):
        pass
    return None


def moves_of(game, chara):
    """The names of a character's special moves (English list), read without keeping the costume in memory."""
    entries = pak.read(game.original(CHARA_FIRST + chara * 10))
    return [n.strip() for _, n in movetext.specials(movetext.decode(entries[movetext.LANGS["en"][0]]))]


def make(game, progress=None):
    """Reads what cache.json keeps and saves it. Slow the first time (161 files): call it from a thread."""
    moves = []
    for c in range(CHARA_COUNT):
        moves.append(moves_of(game, c))
        if progress:
            progress(c)
    grid = menunames.read_grid(game.original(menunames.GRID_FILE))
    data = {"key": _key(game), "moves": moves, "grid": grid}
    try:
        with open(os.path.join(cache_dir(game), "cache.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass
    return data


def label(moves):
    """A short label from a character's moves: the Ultimate, then the first Blast 2."""
    names = [n for n in moves if n != "Hyper Smash"]
    if not names:
        return ""
    return names[-1] + (" · " + names[2] if len(names) >= 5 else "")


# ---- pictures ------------------------------------------------------------------------------------------------------
def chips_path(game, size):
    return os.path.join(cache_dir(game), "chips_%d.png" % size), os.path.join(cache_dir(game), "chips_%d.json" % size)


def chips_ready(game, size):
    path, meta = chips_path(game, size)
    try:
        with open(meta, encoding="utf-8") as f:
            return os.path.exists(path) and json.load(f) == _key(game)
    except (OSError, ValueError):
        return False


def _chip_pack(game):
    """The chips pack (165 texture files, one per character id) of the quickest menu archive."""
    data = game.original(CHIPS_FILE)
    for _, _, raw in menunames._sections(data):
        for k, a, b in menunames._parts(raw):
            if menunames._is_chips(raw, a, b):
                return raw[a:b]
    raise ValueError("no chips in archive %d" % CHIPS_FILE)


def make_chips(game, size):
    """Makes chips_<size>.png: every character's chip, size x size, COLS per row. Call it from a thread."""
    sub = _chip_pack(game)
    n = struct.unpack_from("<I", sub, 0)[0]
    offs = struct.unpack_from("<%dI" % (n + 1), sub, 4)
    rows = (CHARA_COUNT + COLS - 1) // COLS
    W, H = COLS * size, rows * size
    sheet = bytearray(W * H * 4)
    for c in range(CHARA_COUNT):
        w, h, px = images.texture(sub[offs[c]:offs[c + 1]])
        if (w, h) != (size, size):
            px = images.resize(w, h, px, size, size)
        ox, oy = (c % COLS) * size, (c // COLS) * size
        for y in range(size):
            p = ((oy + y) * W + ox) * 4
            sheet[p:p + size * 4] = px[y * size * 4:(y + 1) * size * 4]
    path, meta = chips_path(game, size)
    with open(path, "wb") as f:
        f.write(images.png(W, H, bytes(sheet)))
    with open(meta, "w", encoding="utf-8") as f:
        json.dump(_key(game), f)
    return path


FACES = "faces2_%d"      # (2: the top edge fades; the folders of older versions are removed)


def face_ready(game, chara, width=256):
    return os.path.exists(os.path.join(cache_dir(game), FACES % width, "%03d.png" % chara))


def mod_face(data, width=256):
    """PNG of a mod's large picture (its portrait file, in the game's own format), `width` wide; not kept (a mod's
    picture is made on demand: it is quick, and the library is its own place)."""
    from . import bpe
    w, h, px = images.texture(bpe.decode(data))
    px = images.fade_top(w, h, px, h // 7)
    if w != width:
        h, px = h * width // w, images.resize(w, h, px, width, h * width // w)
    return images.png(width, h, px, level=1)


def face(game, chara, width=256):
    """PNG of a character's large picture of the select screens, whole (the drawing is cut at the picture's edges,
    the game shows it in a frame of that width; a cut at the top fades in) and `width` wide; kept in the cache
    folder after the first time."""
    path = os.path.join(cache_dir(game), FACES % width, "%03d.png" % chara)
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        pass
    w, h, px = images.face(game.original, chara)
    px = images.fade_top(w, h, px, h // 7)
    if w != width:
        h, px = h * width // w, images.resize(w, h, px, width, h * width // w)
    data = images.png(width, h, px, level=1)
    try:
        old = os.path.join(cache_dir(game), "faces_%d" % width)
        if os.path.isdir(old):
            import shutil
            shutil.rmtree(old, ignore_errors=True)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    except OSError:
        pass
    return data
