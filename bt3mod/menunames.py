"""Character names and grid portraits of the menus.

Every menu screen that lists characters carries its own copies, in the menu archives (pzs3us1 files 448..509: packs
of byte-pair-encoded sections, or a whole byte-pair-encoded file):
  - name lists: 168 fixed slots of 64 bytes (a UTF-16 byte order mark, up to 30 characters, zeros), one line per
    character id (161..167: the grid's markers and leftovers); a "form" list is the same with the form names
    (e.g. the character select: archive 448, section 1, 0-based parts 42 = names and 43 = forms; CharSel_Init,
    source/src/menu/menu_c_e.c, takes them with MPACK_AT(res, 43 / 44): MPACK_AT is 1-based);
  - grid portraits: a pack of 165 pictures of one fixed size, 0-based entry n is character n's;
  - the grid: 16 bytes (u32 cell count, zeros) and the cells {s32 id, formCount, form[7]} (forms.py; CharSel_Init
    takes it with MPACK_AT(res, 42) + 0x10).
They are found by scanning (scan(), cached in menu_map.json next to the tool) rather than by a fixed list.
Changing them keeps every size: only the packed blocks that hold changed bytes are stored again (bpe.patch).
"""
import json
import os
import struct

from . import bpe, pak

SLOT = 64
LINES = 168
MAX_CHARS = 30
CHIPS = 165
FIRST, LAST = 448, 509          # the menu archives
REF_NAME = (152, "Pilaf Machine")  # a line that tells a name list (the name of character 152)
REF_FORM = (160, "Super Saiyan")   # a line that tells a form list
CELL = 36
GRID_HEAD = 16
VERSION = 2                     # of the cache (2: the grids)
GRID_FILE = 454                 # the quickest archive to read a grid from (one packed file; every copy is the same)


def check(name):
    if len(name) > MAX_CHARS:
        raise ValueError(f"« {name} » : {MAX_CHARS} caractères au plus dans les menus")
    name.encode("utf-16-le")


# ---- reading the archives ----------------------------------------------------------------------------------------
def _sections(data):
    """[(section index or None, packed bytes, expanded bytes)] of an archive file."""
    out = []
    cands = list(enumerate(pak.read(data))) if pak.is_pak(data) else [(None, data)]
    for i, sec in cands:
        if len(sec) < 8:
            continue
        try:
            out.append((i, sec, bpe.decode(sec)))
        except Exception:
            pass
    return out


def _parts(raw):
    if not pak.is_pak(raw):
        return []
    n = struct.unpack_from("<I", raw, 0)[0]
    offs = struct.unpack_from("<%dI" % (n + 1), raw, 4)
    return [(k, offs[k], offs[k + 1]) for k in range(n)]


def _line(raw, start, line):
    lo = struct.unpack_from("<I", raw, start + 4 + 4 * line)[0]
    p = start + lo
    return p, raw[p:p + SLOT].decode("utf-16-le", "replace").split("\0")[0].lstrip("﻿")


def _list_kind(raw, start, end):
    """"names" / "forms" when the part is a 168-line list of 64-byte slots, else None."""
    if end - start < 4 + 4 * (LINES + 1) or struct.unpack_from("<I", raw, start)[0] != LINES:
        return None
    offs = struct.unpack_from("<%dI" % (LINES + 1), raw, start + 4)
    if any(offs[k + 1] - offs[k] != SLOT for k in range(LINES)):
        return None
    if _line(raw, start, REF_NAME[0])[1] == REF_NAME[1]:
        return "names"
    if _line(raw, start, REF_FORM[0])[1] == REF_FORM[1] and _line(raw, start, 0)[1] == "":
        return "forms"
    return None


def _is_chips(raw, start, end):
    sub = raw[start:end]
    if not pak.is_pak(sub) or struct.unpack_from("<I", sub, 0)[0] != CHIPS:
        return False
    offs = struct.unpack_from("<%dI" % (CHIPS + 1), sub, 4)
    sizes = {offs[k + 1] - offs[k] for k in range(CHIPS)}
    return len(sizes) == 1 and sizes.pop() > 256


def _grid_cells(raw, start, end):
    """The cells when the part is a character grid, else None."""
    if end - start < GRID_HEAD + CELL:
        return None
    n = struct.unpack_from("<I", raw, start)[0]
    if not 2 <= n <= CHIPS or not 0 <= end - start - GRID_HEAD - n * CELL < 64 or any(raw[start + 4:start + 16]):
        return None
    cells = [struct.unpack_from("<9i", raw, start + GRID_HEAD + CELL * k) for k in range(n)]
    for c in cells:
        if not 0 <= c[0] <= 0xA4 or not 0 <= c[1] <= 7 or any(not 0 <= f < 0xA1 for f in c[2:2 + c[1]]):
            return None
    return cells if any(c[1] for c in cells) else None


def scan(read, sizes):
    """{file index: [(section, kind, part)]} for the menu archives; read(idx) gives a file's bytes, sizes(idx) its
    size (the cache is keyed by sizes)."""
    out = {}
    for idx in range(FIRST, LAST + 1):
        found = []
        for sec, _, raw in _sections(read(idx)):
            for k, a, b in _parts(raw):
                kind = (_list_kind(raw, a, b) or ("chips" if _is_chips(raw, a, b) else None)
                        or ("grid" if _grid_cells(raw, a, b) else None))
                if kind:
                    found.append((sec, kind, k))
        if found:
            out[idx] = found
    return out


def _sizes(root):
    return {idx: os.path.getsize(os.path.join(root, "pzs3us1", "%05d.bin" % idx)) for idx in range(FIRST, LAST + 1)}


def cached(root, cache_dir):
    """menu_map's result when cache_dir/menu_map.json is there and up to date, else None (no scan)."""
    try:
        with open(os.path.join(cache_dir, "menu_map.json"), encoding="utf-8") as f:
            c = json.load(f)
        if c.get("sizes") == {str(k): v for k, v in _sizes(root).items()} and c.get("version") == VERSION:
            return ({int(k): [tuple(x) for x in v] for k, v in c["map"].items()},
                    {int(k): v for k, v in c["tables"].items()}, c["lists"])
    except (OSError, ValueError):
        pass
    return None


def menu_map(root, read, cache_dir):
    """The scan's result, cached in cache_dir/menu_map.json (made again when a menu archive's size changed)."""
    c = cached(root, cache_dir)
    if c is not None:
        return c
    sizes = _sizes(root)
    path = os.path.join(cache_dir, "menu_map.json")
    m = scan(read, sizes)
    tables = {idx: block_tables(read(idx), where) for idx, where in m.items()}
    lists = {kind: read_names(read(FIRST), kind) for kind in ("names", "forms")}  # the disc's own names
    lists["grid"] = read_grid(read(FIRST))  # (and its character select grid)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"version": VERSION, "sizes": sizes, "map": m, "tables": tables, "lists": lists}, f)
    except OSError:
        pass
    return m, tables, lists


def read_names(data, kind="names"):
    """The names (or forms) of the first such list of an archive."""
    for _, _, raw in _sections(data):
        for k, a, b in _parts(raw):
            if _list_kind(raw, a, b) == kind:
                return [_line(raw, a, n)[1] for n in range(LINES)]
    raise ValueError("no %s list in this archive" % kind)


def read_grid(data):
    """The cells [id, formCount, form x 7] of the largest grid of an archive (the character select's: 99 cells; a
    screen may hold a small one too)."""
    best = []
    for _, _, raw in _sections(data):
        for k, a, b in _parts(raw):
            cells = _grid_cells(raw, a, b) or []
            if len(cells) > len(best):
                best = cells
    if not best:
        raise ValueError("no grid in this archive")
    return [list(c) for c in best]


# ---- changing them ----------------------------------------------------------------------------------------------
def block_tables(data, where):
    """{section: block table} of the sections `where` names (kept in the cache: computing them is the slow part)."""
    entries = pak.read(data) if pak.is_pak(data) else None
    return {str(sec): bpe.blocks(entries[sec] if entries is not None else data) for sec in {w[0] for w in where}}


def apply(data, where, names=None, forms=None, chips=None, tables=None, cells=None):
    """The archive `data` with its lists renamed (names / forms: {character id: text}), grid portraits copied
    (chips: {character id: character id whose portrait it takes}) and the forms of grid cells changed (cells:
    {character id heading a cell: [form ids]}); `where` = [(section, kind, part)] from scan."""
    for t in list((names or {}).values()) + list((forms or {}).values()):
        check(t)
    entries = list(pak.read(data)) if pak.is_pak(data) else None
    secs = {}
    for sec, kind, part in where:
        secs.setdefault(sec, []).append((kind, part))
    for sec, items in secs.items():
        p = bpe.Packed(entries[sec] if entries is not None else data, (tables or {}).get(str(sec)))
        for kind, part in items:
            a = p.u32(4 + 4 * part)  # the part's start (the expanded section is a pack)
            if kind in ("names", "forms"):
                for line, text in ((names if kind == "names" else forms) or {}).items():
                    pos = a + p.u32(a + 4 + 4 * int(line))
                    p.write(pos, (b"\xff\xfe" + text.encode("utf-16-le")).ljust(SLOT, b"\0"))
            elif kind == "chips" and chips:
                for dst, src in chips.items():
                    da, db = p.u32(a + 4 + 4 * int(dst)), p.u32(a + 8 + 4 * int(dst))
                    sa, sb = p.u32(a + 4 + 4 * int(src)), p.u32(a + 8 + 4 * int(src))
                    if db - da != sb - sa:
                        raise ValueError("menus: grid portraits of different sizes")
                    p.write(a + da, p.read(a + sa, sb - sa))
            elif kind == "grid" and cells:
                n = p.u32(a)
                for k in range(n):
                    at = a + GRID_HEAD + CELL * k
                    want = cells.get(struct.unpack("<i", p.read(at, 4))[0])
                    if want is not None:
                        # (a one-character cell: count 0, the character in form[0], as on the disc)
                        fs = list(want)
                        p.write(at + 4, struct.pack("<8i", len(fs) if len(fs) > 1 else 0, *(fs + [0] * (7 - len(fs)))))
        new = p.bytes()
        if entries is not None:
            entries[sec] = new
        else:
            data = new
    return pak.write(entries) if entries is not None else data
