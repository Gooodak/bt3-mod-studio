"""Transformations of a character and the forms its cell of the character grid offers.

Transformations live in the general parameters (costume entry 17, BtlParam, source/include/battle/btl_tech_a.h):
four slots, one per R3 direction (BtlAct_CheckTransformInput, source/src/battle/btl_act_j.c: left, up, right = 0..2
go up a form, down = 3 goes back), each {target character id (0xFF = none) @0x98, cost in blast stocks @0x9C,
sequence @0xA0 (the action played: 0xEC + seq), kind @0xA4 (the effect: 2 = Super Saiyan, 3 = great ape (needs the
moon), 8 = Frieza-like...), @0xA8 (Cell: the android absorbed)}, the slot a neutral R3 takes @0xAC and a "keep the
damaged look" bit per slot @0xAD (bit 4 + slot, BtlParam_TestUnkADBit). The target is an absolute character id: a
copy of Super Vegeta goes back to the real Vegeta (31) unless the pack says otherwise.

The grid (character select and the other screens that list characters: menunames.py finds them) is a list of
cells {id, formCount, form[7]} (MChrCell, source/include/menu/menu_d.h); formCount 0 = the cell is the one
character, else the forms the player picks from before the battle (Goku (End): Goku, SSJ, SSJ2, SSJ3, the fusions).
"""
SLOTS = 4
BACK = 3            # slot 3: R3 + down, back to the base form
NONE = 0xFF
TARGET, COST, SEQ, KIND, A8 = 0x98, 0x9C, 0xA0, 0xA4, 0xA8
DEFAULT, AD = 0xAC, 0xAD
MAX_FORMS = 7
MAX_COST = 7        # blast stocks (the gauge has 7)


def read(param):
    """[{"to", "cost", "seq", "kind", "a8", "keep"} or None] x 4 of a general parameters block."""
    out = []
    for i in range(SLOTS):
        if param[TARGET + i] == NONE:
            out.append(None)
        else:
            out.append({"to": param[TARGET + i], "cost": param[COST + i], "seq": param[SEQ + i],
                        "kind": param[KIND + i], "a8": param[A8 + i], "keep": (param[AD] >> (4 + i)) & 1})
    return out


def write(param, slots):
    """The block with these 4 slots (from read() / resolve()); the neutral R3 goes to the first upward one."""
    p = bytearray(param)
    ad = p[AD] & 0x0F
    for i, s in enumerate(slots):
        if s is None:
            p[TARGET + i] = NONE
            continue
        p[TARGET + i], p[COST + i], p[SEQ + i], p[KIND + i], p[A8 + i] = \
            s["to"], s["cost"], s["seq"], s["kind"], s["a8"]
        ad |= s.get("keep", 0) << (4 + i)
    p[AD] = ad
    up = [i for i in range(BACK) if slots[i] is not None]
    p[DEFAULT] = up[0] if up else NONE
    return bytes(p)


def templates(params):
    """{target: slot settings} the disc uses to reach each character (the first one found, upward slots first):
    a new transformation into that character plays the same sequence and effect."""
    up, back = {}, {}
    for p in params:
        for i, s in enumerate(read(p)):
            if s is not None:
                (back if i == BACK else up).setdefault(s["to"], s)
    return up, back


def resolve(chosen, own, up, back):
    """The 4 slots the pack asks for: chosen = [{"to", "cost"} or None] x 4. A target the character already has in
    that slot keeps its own settings; another one takes the disc's way to reach it (templates), else a plain one."""
    out = []
    for i, c in enumerate(chosen):
        if c is None:
            out.append(None)
            continue
        to = int(c["to"])
        if own[i] is not None and own[i]["to"] == to:
            s = dict(own[i])
        elif i == BACK:
            s = dict(back.get(to) or {"seq": 1, "kind": 1, "a8": NONE, "keep": 0})
        else:
            s = dict(up.get(to) or {"seq": 0, "kind": 1, "a8": NONE, "keep": 0})
            if s["kind"] == 1 and s["seq"] == 1:  # (a "back" settings found upward: play a plain change)
                s["seq"] = 0
        s["to"] = to
        s["cost"] = max(0, min(MAX_COST, int(c.get("cost", s.get("cost", 1)))))
        out.append(s)
    return out


def remap(slots, clones):
    """The slots with their targets moved to this pack's copies of them (clones: {original id: copy id})."""
    return [None if s is None else dict(s, to=clones.get(s["to"], s["to"])) for s in slots]


def chosen(slots):
    """The pack's form of slots: [{"to", "cost"} or None] x 4."""
    return [None if s is None else {"to": s["to"], "cost": s["cost"]} for s in slots]


# ---- the grid ---------------------------------------------------------------------------------------------------
def cell_forms(cell):
    """The characters a cell offers (its id alone when it has no form list)."""
    return list(cell[2:2 + cell[1]]) if cell[1] else [cell[0]]


def cell_of(grid, chara):
    """The cell headed by chara (its id), or None: a character that is only a form of another cell has none."""
    for cell in grid:
        if cell[0] == chara:
            return cell
    return None


def default_forms(grid, chara, base, params_of, clones):
    """The forms the cell of `chara` (a copy of `base`) offers: the base's cell when the base heads one, else the
    base and the forms its transformations reach; with the pack's copies (clones: {original: copy}) in place of
    their originals. params_of(id) gives a character's original general parameters."""
    m = dict(clones)
    m[base] = chara
    cell = cell_of(grid, base)
    if cell is not None:
        found = cell_forms(cell)
    else:
        found, todo = [], [base]
        while todo and len(found) < MAX_FORMS:
            o = todo.pop(0)
            if o not in found:
                found.append(o)
                todo += [s["to"] for s in read(params_of(o))[:BACK] if s is not None]
    out = [chara]
    for f in found:
        f = m.get(f, f)
        if f not in out:
            out.append(f)
    return out[:MAX_FORMS]
