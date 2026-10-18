"""Moving a whole special move (Blast 2 / Ultimate, or Blast 1) from one character to another.

A technique slot (2, 3: the two Blast 2 moves; 4: the Ultimate) is made of:
  - its column of the technique table (costume entry 23, BtlSuperData: a structure of arrays of 3);
  - the model motions and character cameras it may use (costume entries 28..39, see EXTRAS);
  - its 0x22 animations (animation pack, entries 0x105 + (slot - 2) * 0x22 ..: source/src/battle/btl_act_f.c);
  - its effect (effect pack entry `slot`: EftShot_GetCharPack -> BObjMdl.unk84, a self-contained sub-pack);
  - its name in the move list.
A Blast 1 ("skill", slots 0, 1; grafts with "kind": "skill") is the same in smaller: its column of the skill table
(costume entry 24, BtlSkillData, arrays of 2: SKILL_LAYOUT), its one animation (0x103 + slot), its effect (effect
pack entry `slot`) and its name.
The voice lines and the technique sounds stay the target's own (they live in the character's sound banks).
"""
from . import fields, movetext, pak

ANIM_BASE = 0x105
ANIM_COUNT = 0x22
# Costume entries a technique may use besides its own data (BObjMdl, source/include/battle/bobj_b.h; BObjFile_GetEntry
# is 1-based, these are 0-based): 28..35 the model's own motions (unk720, entries 0x1D..0x24), 36..39 the character's
# camera animations (unk8F0, entries 0x25..0x28: DemoCam_PlayCharAnim0..2 on fighter flags 0xD7..0xD9). Entries
# 40..42 (unk98) are NOT technique cameras: the intro and victory cameras of the battle sequence (btl_seq.c).
# Entry 35 is left out: every character has one (its own, not a technique's).
EXTRAS = [i for i in range(28, 40) if i != 35]


class IncompatibleGraft(Exception):
    """The technique needs a costume entry the target character already uses for something else."""

    def __init__(self, entry):
        super().__init__(entry)
        self.entry = entry
ULTIMATE = 2          # technique slot 4, the third column
ULTIMATE_POSE = 0x16B

# BtlSuperData as (offset, element size, array count): every array has 3 elements, one per slot. Known fields from
# source/include/battle/btl_tech_b.h; element sizes of the unknown regions inferred from techniques two characters
# have in different slots (all 59 such pairs agree), the 60-byte tail is zero for every character.
SUPER_LAYOUT = [
    (0x000, 4, 2),   # flagsA, flags
    (0x018, 2, 2),   # id, unk1E
    (0x024, 4, 1),   # shotTime
    (0x030, 4, 3),   # unknown
    (0x054, 4, 3),   # shotSpeed, shotTurn, shotUnk6C
    (0x078, 4, 2),   # unknown
    (0x090, 1, 5),   # unk90, shots, hitsB, unk99, hitsC
    (0x09F, 1, 52),  # unknown bytes
    (0x13B, 1, 16),  # hitDirKind .. lastStep (hitSound is [2][3])
    (0x16C, 4, 13),  # push .. rushSpeed
    (0x208, 2, 2),   # throwChara, throwCharaAlt
    (0x214, 4, 1),   # unknown
    (0x220, 1, 4),   # unk220, unk223, unk226, promptRow
    (0x22C, 4, 2),   # time22C, time238
]
SUPER_END = 0x244

# BtlSkillData (source/include/battle/btl_tech_b.h) as (offset, element size, array count), arrays of 2. The element
# sizes of the unknown regions: those the same Blast 1 in the two slots of two characters agrees with (every other
# size gives no agreement at all); 0xC8..0x100 is zero for every character.
SKILL_LAYOUT = [
    (0x00, 4, 2),   # flagsA, flags
    (0x10, 2, 2),   # id, unk14
    (0x18, 4, 4),   # shotTime, shotSpeed, shotTurn, shotUnk30
    (0x38, 1, 5),   # unk38, shots, hitsB, unk3E, hitsC
    (0x42, 1, 16),  # unknown bytes
    (0x62, 1, 6),   # hitDirKind, sequence, statKind, react, reactS800, hitSound
    (0x6E, 1, 3),   # unknown bytes
    (0x74, 4, 2),   # push, guardPush
    (0x84, 4, 2),   # damage, guardDamage
    (0x94, 1, 6),   # stocks, statLevel0, statLevel2, statLevel1, statLevel3, unk9E
    (0xA0, 4, 5),   # time, healthPct, ki, valF, valE
]
SKILL_END = 0xC8
SKILL_ANIM = 0x103


def _check_layout():
    for layout, n, end in ((SUPER_LAYOUT, 3, SUPER_END), (SKILL_LAYOUT, 2, SKILL_END)):
        pos = 0
        for off, size, count in layout:
            if off < pos:
                raise AssertionError(f"layout overlaps at {off:#x}")
            pos = off + size * n * count
        assert pos == end, hex(pos)


_check_layout()


def is_skill(graft):
    """A graft of a Blast 1 (else of a Blast 2 / the Ultimate)."""
    return graft.get("kind") == "skill"


def _copy_column(dst, src, dst_slot, src_slot, layout, n):
    """Copies one column of a structure of arrays of n (layout: (offset, element size, array count))."""
    out = bytearray(dst)
    for off, size, count in layout:
        for k in range(count):
            base = off + k * size * n
            a = base + dst_slot * size
            b = base + src_slot * size
            out[a:a + size] = src[b:b + size]
    return bytes(out)


def copy_super_slot(dst, src, dst_slot, src_slot):
    """Copies one technique column (slots 0..2 = technique slots 2..4) from table src into table dst."""
    return _copy_column(dst, src, dst_slot, src_slot, SUPER_LAYOUT, 3)


def copy_skill_slot(dst, src, dst_slot, src_slot):
    """Copies one Blast 1 column (slots 0..1) from table src into table dst."""
    return _copy_column(dst, src, dst_slot, src_slot, SKILL_LAYOUT, 2)


def anim_range(slot):
    """Animation pack entries of technique slot 0..2."""
    start = ANIM_BASE + slot * ANIM_COUNT
    return range(start, start + ANIM_COUNT)


def apply_to_costume(entries, src_entries, dst_slot, src_slot, skill=False):
    """Costume pack part of a transplant, in place on a list of entries (skill: a Blast 1, slots 0..1)."""
    if skill:
        entries[fields.ENTRY_SKILL] = copy_skill_slot(entries[fields.ENTRY_SKILL], src_entries[fields.ENTRY_SKILL],
                                                      dst_slot, src_slot)
    else:
        entries[fields.ENTRY_SUPER] = copy_super_slot(entries[fields.ENTRY_SUPER], src_entries[fields.ENTRY_SUPER],
                                                      dst_slot, src_slot)
    # The technique may play the model's own motions and camera animations of its character (entries 28..39): they
    # come along where the target has none. A target that has its own there keeps them: that technique cannot come.
    for i in EXTRAS:
        if not src_entries[i]:
            continue
        if not entries[i]:
            entries[i] = src_entries[i]
        elif entries[i] != src_entries[i]:
            raise IncompatibleGraft(i)
    first = 0 if skill else 2
    for lang, (ent, _) in movetext.LANGS.items():
        dst_text = movetext.decode(entries[ent])
        src_names = movetext.specials(movetext.decode(src_entries[ent]))
        dst_names = movetext.specials(dst_text)
        # the standard list is Blast 1 x2, Blast 2 x2, Ultimate, Hyper Smash: Blast 1 n is name n, technique n is 2 + n
        if len(src_names) == 6 and len(dst_names) == 6:
            dst_text = movetext.rename(dst_text, first + dst_slot, src_names[first + src_slot][1])
            entries[ent] = movetext.encode(dst_text)


def apply_to_anims(entries, src_entries, dst_slot, src_slot, skill=False):
    if skill:  # one animation per Blast 1 (BtlSkill_PlayAnim, source/src/battle/btl_act_h_b.c)
        entries[SKILL_ANIM + dst_slot] = src_entries[SKILL_ANIM + src_slot]
        return
    for d, s in zip(anim_range(dst_slot), anim_range(src_slot)):
        entries[d] = src_entries[s]
    # An Ultimate starts with its own pose, motion 0x16B (BtlAct_UltimateStartHandler, source/src/battle/btl_act_f.c).
    # A Blast 2 has none: an Ultimate made from one keeps the target's pose.
    if dst_slot == ULTIMATE and src_slot == ULTIMATE:
        entries[ULTIMATE_POSE] = src_entries[ULTIMATE_POSE]


# The character's general effect pack (effect pack entry 5, BtlScene_GetCharPackEntry) holds in its entry 7 one camera
# cut per technique slot (entries 0, 1, 2 for slots 2, 3, 4): EftRushShotMgr_Init (source/src/battle/eft_k.c) takes
# them, and a technique that expects one and finds none crashes in DemoCam_SetAnim.
GENERAL = 5
TECH_CAMS = 7


def _sub(data, n):
    """The entries of a pack, at least n of them (an empty entry stands for a missing pack)."""
    e = list(pak.read(data)) if data and pak.is_pak(data) else []
    return e + [b""] * (n - len(e))


def apply_to_effects(entries, src_entries, dst_slot, src_slot, skill=False):
    if skill:  # effect pack entries 0 and 1 (the same Blast 1 in another slot of another character: the same bytes)
        entries[dst_slot] = src_entries[src_slot]
        return
    entries[2 + dst_slot] = src_entries[2 + src_slot]
    dst_gen, src_gen = _sub(entries[GENERAL], TECH_CAMS + 1), _sub(src_entries[GENERAL], TECH_CAMS + 1)
    dst_cams, src_cams = _sub(dst_gen[TECH_CAMS], 4), _sub(src_gen[TECH_CAMS], 4)
    if dst_cams[dst_slot] != src_cams[src_slot]:
        dst_cams[dst_slot] = src_cams[src_slot]
        dst_gen[TECH_CAMS] = pak.write(dst_cams)
        entries[GENERAL] = pak.write(dst_gen)
