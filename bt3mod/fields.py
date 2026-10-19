"""The editable values of a character, read from its costume pack.

Layouts come from the decompilation (source/include/battle/btl_tech_b.h); the costume-pack entry of each table
from BtlObj binding code (source/src/battle/bobj_a.c, BObjFile_GetEntry is 1-based, the indexes here are 0-based).
Every costume of a character carries the same tables, so a change is written to all of them.
"""
import struct
from dataclasses import dataclass

# 0-based entries of the costume pack
ENTRY_PARAM = 17    # general parameters (BtlParam / BtlTechBParam)
ENTRY_KIBLAST = 19  # 13 ki blast records of 0x34 bytes
ENTRY_MOVE = 20     # movement (BtlMoveData)
ENTRY_SUPER = 23    # Blast 2 x2 + Ultimate (BtlSuperData, structure of arrays, 3 slots)
ENTRY_SKILL = 24    # Blast 1 x2 (BtlSkillData, structure of arrays, 2 slots)

HP_BAR = 10000      # health points in one bar of health
KI_BAR = 20000      # ki units in one bar of ki (100000 = the full gauge of 5 bars)

_FMT = {"s8": "b", "u8": "B", "s16": "h", "u16": "H", "s32": "i", "u32": "I", "f32": "f"}


@dataclass(frozen=True)
class Field:
    key: str        # stable id used in mod packs, e.g. "super.damage.2"
    group: str      # tab in the editor
    slot: str       # what it belongs to (e.g. "Ultime")
    label: str      # French label
    entry: int      # costume pack entry
    offset: int     # byte offset inside the entry
    type: str       # s8 / s16 / s32 / f32 ...
    hint: str = ""  # unit / help
    lo: float = None
    hi: float = None
    where: str = "costume"  # "costume": the character's costume packs; "roster": its row of the shared table
    kind: str = "value"     # "value": one number; "scale": a percentage applied to many numbers (see game.py)
    hidden: bool = False    # not shown: tried in the test game, no use (HIDDEN_WHY); dropped from packs on loading

    @property
    def fmt(self):
        return "<" + _FMT[self.type]

    @property
    def is_float(self):
        return self.type == "f32"

    def read(self, entries, base=0):
        e = entries[self.entry]
        return struct.unpack_from(self.fmt, e, base + self.offset)[0]

    def write(self, entries, value, base=0):
        e = bytearray(entries[self.entry])
        value = float(value) if self.is_float else int(round(float(value)))
        struct.pack_into(self.fmt, e, base + self.offset, value)
        entries[self.entry] = bytes(e)

    def clamp(self, value):
        if self.lo is not None and value < self.lo:
            return self.lo
        if self.hi is not None and value > self.hi:
            return self.hi
        return value


SUPER_SLOTS = ["Blast 2 n°1", "Blast 2 n°2", "Ultime"]
SKILL_SLOTS = ["Blast 1 n°1", "Blast 1 n°2"]
# (source/include/battle/btl_tech_b.h BTL_KIBLAST_*, and the actions that play their animations: 0xAE standing,
# 0xB0 while dashing, 0xB2 aimed down from the air, 0x95 the ki volley of a combo)
KIBLAST_NAMES = [
    "Tir de ki", "Tir de ki chargé (un peu)", "Tir de ki chargé (moyen)", "Tir de ki chargé (à fond)",
    "Tir en dash", "Tir en dash chargé (un peu)", "Tir en dash chargé (moyen)", "Tir en dash chargé (à fond)",
    "Tir vers le bas (en l'air)", "Vers le bas chargé (un peu)", "Vers le bas chargé (moyen)",
    "Vers le bas chargé (à fond)",
    "Salve de ki (combo)",
]

S32 = 2 ** 31 - 1
FIELDS = []

# ---- Blast 2 and Ultimate: arrays of 3 (one per slot) --------------------------------------------------------
_SUPER = [
    # name,        offset, type, stride, label, hint, lo, hi
    ("damage",      0x184, "s32", 4, "Dégâts", "10000 = 1 barre de vie", 0, S32),
    ("guardDamage", 0x190, "s32", 4, "Dégâts si l'adversaire garde", "10000 = 1 barre de vie", 0, S32),
    ("ki",          0x19C, "s32", 4, "Coût en ki", "20000 = 1 barre de ki (jauge pleine = 100000)", 0, 100000),
    ("recoil",      0x1A8, "s32", 4, "Dégâts subis par le lanceur", "10000 = 1 barre de vie", 0, S32),
    ("push",        0x16C, "f32", 4, "Puissance de recul", "x10 km/h", 0, 10000),
    ("shotSpeed",   0x054, "f32", 4, "Vitesse du projectile", "x10 km/h ; plus lent se voit bien, plus rapide "
                                                                 "peu (l'animation garde son rythme)", 0, 10000),
    ("shotTime",    0x024, "f32", 4, "Durée de vie du projectile", "secondes", 0, 60),
    ("shotTurn",    0x060, "f32", 4, "Guidage du projectile", "degrés par seconde", 0, 3600),
    ("chargeScale", 0x1D8, "f32", 4, "Multiplicateur à charge maximale", "1.5 = +50 %", 0, 100),
    ("shots",       0x093, "s8",  1, "Nombre de projectiles", "1 à 127", 1, 127),
]
for slot, slot_name in enumerate(SUPER_SLOTS):
    for name, off, typ, stride, label, hint, lo, hi in _SUPER:
        FIELDS.append(Field(f"super.{name}.{slot}", "Blast 2 & Ultime", slot_name, label, ENTRY_SUPER,
                            off + slot * stride, typ, hint, lo, hi, hidden=name == "shots"))

# ---- Blast 1 (skills): arrays of 2 -----------------------------------------------------------------------------
_SKILL = [
    ("stocks",     0x94, "s8",  1, "Coût en blast stocks", "0 à 7", 0, 7),
    ("time",       0xA0, "f32", 4, "Durée de l'effet", "secondes", 0, 600),
    ("statLevel0", 0x96, "s8",  1, "Bonus d'attaque", "niveaux, -9 à 9", -9, 9),
    ("statLevel1", 0x9A, "s8",  1, "Bonus de défense (supposé)", "niveaux, -9 à 9", -9, 9),
    ("statLevel2", 0x98, "s8",  1, "Bonus de vitesse", "niveaux, -9 à 9", -9, 9),
    ("statLevel3", 0x9C, "s8",  1, "Bonus de puissance des blasts", "niveaux, -9 à 9", -9, 9),
    ("healthPct",  0xA8, "s32", 4, "Vie rendue", "% de la vie max (négatif = perdue)", -100, 100),
    ("damage",     0x84, "s32", 4, "Dégâts", "10000 = 1 barre de vie", 0, S32),
]
for slot, slot_name in enumerate(SKILL_SLOTS):
    for name, off, typ, stride, label, hint, lo, hi in _SKILL:
        FIELDS.append(Field(f"skill.{name}.{slot}", "Blast 1", slot_name, label, ENTRY_SKILL,
                            off + slot * stride, typ, hint, lo, hi))

# ---- Ki blasts: 13 records of 0x34 bytes ----------------------------------------------------------------------
_KIB = [
    ("damage", 0x04, "s32", "Dégâts", "10000 = 1 barre de vie", 0, S32),
    ("guardDamage", 0x08, "s32", "Dégâts si l'adversaire garde", "10000 = 1 barre de vie", 0, S32),
    ("ki",     0x0C, "s32", "Coût en ki", "20000 = 1 barre de ki", 0, 100000),
    ("speed",  0x10, "f32", "Vitesse", "x10 km/h : le temps que met le tir à arriver", 0, 10000),
    ("turn",   0x14, "f32", "Guidage", "degrés par seconde", 0, 3600),
    ("time",   0x18, "f32", "Durée de vie", "secondes", 0, 60),
    ("hits",   0x30, "s8",  "Nombre de coups", "1 à 127", 1, 127),
]
for k, kname in enumerate(KIBLAST_NAMES):
    for name, off, typ, label, hint, lo, hi in _KIB:
        FIELDS.append(Field(f"kiblast.{name}.{k}", "Rafales de ki", kname, label, ENTRY_KIBLAST,
                            k * 0x34 + off, typ, hint, lo, hi, hidden=name == "hits"))

# ---- General ----------------------------------------------------------------------------------------------------
# The shared character table: common file 2 (pzs3us1/00001.bin), entry 7, one 16-byte row per character
# (BtlMemberParam in source/include/battle/btl_char_member.h; bound in btl_char_mgr.c as gBtlChars->tbl[4]).
ROSTER_FILE = 1
ROSTER_ENTRY = 7
ROSTER_ROW = 16
FIELDS.append(Field("roster.health", "Général", "Vie, ki et blast stocks", "Vie maximale", ROSTER_ENTRY, 0x0, "s32",
                    "10000 = 1 barre ; l'écran en montre 7 au plus, au-delà la vie compte quand même",
                    10000, 150000, where="roster"))
FIELDS.append(Field("roster.kiStart", "Général", "Vie, ki et blast stocks", "Ki au début du combat", ROSTER_ENTRY, 0x4,
                    "s32", "20000 = 1 barre (jauge pleine = 100000)", 0, 100000, where="roster"))
FIELDS.append(Field("roster.stocks", "Général", "Vie, ki et blast stocks", "Nombre de blast stocks", ROSTER_ENTRY, 0xC,
                    "s32", "1 à 7", 1, 7, where="roster"))

FIELDS.append(Field("melee.damageScale", "Général", "Corps à corps", "Dégâts de tous les coups au corps à corps",
                    18, 0, "s32", "% de l'original (100 = inchangé)", 0, 1000, kind="scale"))

FIELDS.append(Field("param.damageTaken", "Général", "Résistance", "Dégâts reçus (multiplicateur)", ENTRY_PARAM,
                    0x7C, "f32", "1.0 = normal, 0.5 = deux fois plus résistant", 0, 100))
FIELDS.append(Field("param.hitReactScale", "Général", "Résistance", "Force des réactions aux coups reçus",
                    ENTRY_PARAM, 0x60, "f32", "1.0 = normal", 0, 100))

_PARAM = [
    ("kiCharge",     0x30, "s32", "Vitesse de charge du ki", "par seconde (20000 = 1 barre)", 0, 1000000),
    ("kiRegen",      0x38, "s32", "Régénération passive du ki", "par seconde", 0, 1000000),
    ("kiRegenLimit", 0x28, "s32", "Niveau où la régénération passive s'arrête", "20000 = 1 barre", 0, 100000),
    ("blastGain",    0x44, "s32", "Gain de blast stocks", "par seconde (100000 = 1 stock)", 0, 1000000),
    ("maxPowerTime", 0x54, "f32", "Durée du mode Max Power", "secondes", 0, 600),
    ("maxPowerChargeTime", 0x50, "f32", "Temps pour remplir la jauge Max Power", "secondes", 0, 600),
]
for name, off, typ, label, hint, lo, hi in _PARAM:
    FIELDS.append(Field(f"param.{name}", "Général", "Ki et Max Power", label, ENTRY_PARAM, off, typ, hint, lo, hi))

ATK_ENTRY = 18      # 0xA3 melee attack records of 0x30 bytes (BtlAtkRecord, source/include/battle/btl_tech_a.h)
ATK_COUNT = 0xA3
ATK_SIZE = 0x30

# ---- Movement: the 20 speeds, by the action handlers that read them (BtlMoveParam_GetSpeed in
# source/src/battle/btl_act_*.c; fighter flag 0x11 = in water picks the odd one of a pair) ----------------------
MOVE_NAMES = [
    "Déplacement", "Déplacement dans l'eau", "Déplacement près de l'adversaire", "Près de l'adversaire, dans l'eau",
    "Dash", "Dash dans l'eau", "Dash droit sur l'adversaire", "Dragon Dash",
    "Dragon Dash : montée", "Montée et descente rapides", "Pas vers l'adversaire", "Pas de côté",
    "Pas de côté : rotation", "Saut : vitesse en l'air", "(inconnue)", "(inconnue)",
    "Montée", "Descente", "Esquive éclair (Vanish)", "Dash en cercle autour de l'adversaire",
]
MOVE_GROUPS = [
    ("Se déplacer", [0, 2, 13, 16, 17, 9]),
    ("Dashs", [4, 6, 7, 8, 19]),
    ("Pas et esquives", [11, 12, 10, 18]),
    ("Dans l'eau", [1, 3, 5]),
]
for i in range(20):
    FIELDS.append(Field(f"move.speed.{i}", "Déplacements", "Vitesses", MOVE_NAMES[i], ENTRY_MOVE, i * 4,
                        "f32", "x10 km/h", 0, 4000, hidden=i in (14, 15)))  # (14, 15: read by no action found)

BY_KEY = {f.key: f for f in FIELDS}
HIDDEN_WHY = {
    "super.shots": "le « nombre de projectiles » d'une technique n'en ajoute pas : il divise les dégâts de chaque "
                   "coup (essayé : Kamehameha, Chou Makouhou Barrage)",
    "kiblast.hits": "le « nombre de coups » d'un tir de ki ne change rien en combat",
    "move.speed": "deux vitesses de déplacement qu'aucune action du jeu ne lit",
}


def drop_hidden(pack):
    """Takes the values of hidden fields out of a pack (they were shown by earlier versions); returns the reasons
    of what was taken out (HIDDEN_WHY), one each."""
    why = []
    for ch in list(pack.get("characters", {}).values()) + list(pack.get("added", [])):
        values = ch.get("fields", {})
        for key in [k for k in values if k in BY_KEY and BY_KEY[k].hidden]:
            del values[key]
            reason = HIDDEN_WHY.get(key.rsplit(".", 1)[0], "")
            if reason and reason not in why:
                why.append(reason)
        if "fields" in ch and not values:
            del ch["fields"]
    return why
GROUPS = ["Général", "Blast 2 & Ultime", "Blast 1", "Rafales de ki", "Déplacements"]


def scale_melee(entries, pct):
    """Multiplies the damage and the guarded damage of every melee attack record by pct / 100."""
    e = bytearray(entries[ATK_ENTRY])
    for r in range(ATK_COUNT):
        for off in (4, 6):  # u16 damage, u16 guardDamage
            p = r * ATK_SIZE + off
            v = struct.unpack_from("<H", e, p)[0]
            struct.pack_into("<H", e, p, min(0xFFFF, int(round(v * pct / 100.0))))
    entries[ATK_ENTRY] = bytes(e)
