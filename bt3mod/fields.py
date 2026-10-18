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
KIBLAST_NAMES = [
    "Rafale A (normale)", "Rafale A chargée niv. 1", "Rafale A chargée niv. 2", "Rafale A chargée niv. 3",
    "Rafale B (normale)", "Rafale B chargée niv. 1", "Rafale B chargée niv. 2", "Rafale B chargée niv. 3",
    "Rafale C (normale)", "Rafale C chargée niv. 1", "Rafale C chargée niv. 2", "Rafale C chargée niv. 3",
    "Salve de ki",
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
    ("shotSpeed",   0x054, "f32", 4, "Vitesse du projectile", "x10 km/h", 0, 10000),
    ("shotTime",    0x024, "f32", 4, "Durée de vie du projectile", "secondes", 0, 60),
    ("shotTurn",    0x060, "f32", 4, "Guidage du projectile", "degrés par seconde", 0, 3600),
    ("chargeScale", 0x1D8, "f32", 4, "Multiplicateur à charge maximale", "1.5 = +50 %", 0, 100),
    ("shots",       0x093, "s8",  1, "Nombre de projectiles", "1 à 127", 1, 127),
]
for slot, slot_name in enumerate(SUPER_SLOTS):
    for name, off, typ, stride, label, hint, lo, hi in _SUPER:
        FIELDS.append(Field(f"super.{name}.{slot}", "Blast 2 & Ultime", slot_name, label, ENTRY_SUPER,
                            off + slot * stride, typ, hint, lo, hi))

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
    ("speed",  0x10, "f32", "Vitesse", "x10 km/h", 0, 10000),
    ("turn",   0x14, "f32", "Guidage", "degrés par seconde", 0, 3600),
    ("time",   0x18, "f32", "Durée de vie", "secondes", 0, 60),
    ("hits",   0x30, "s8",  "Nombre de coups", "1 à 127", 1, 127),
]
for k, kname in enumerate(KIBLAST_NAMES):
    for name, off, typ, label, hint, lo, hi in _KIB:
        FIELDS.append(Field(f"kiblast.{name}.{k}", "Rafales de ki", kname, label, ENTRY_KIBLAST,
                            k * 0x34 + off, typ, hint, lo, hi))

# ---- General ----------------------------------------------------------------------------------------------------
# The shared character table: common file 2 (pzs3us1/00001.bin), entry 7, one 16-byte row per character
# (BtlMemberParam in source/include/battle/btl_char_member.h; bound in btl_char_mgr.c as gBtlChars->tbl[4]).
ROSTER_FILE = 1
ROSTER_ENTRY = 7
ROSTER_ROW = 16
FIELDS.append(Field("roster.health", "Général", "Vie, ki et blast stocks", "Vie maximale", ROSTER_ENTRY, 0x0, "s32",
                    "10000 = 1 barre (de 1 à 7 barres)", 10000, 70000, where="roster"))
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

# ---- Movement: the 20 speeds (their individual meaning is not established yet) ----------------------------------
for i in range(20):
    FIELDS.append(Field(f"move.speed.{i}", "Déplacements", "Vitesses", f"Vitesse n°{i + 1}", ENTRY_MOVE, i * 4,
                        "f32", "x10 km/h (rôle exact pas encore identifié)", 0, 4000))

BY_KEY = {f.key: f for f in FIELDS}
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
