"""Scripted test runs of the real game: the controller input is written beforehand and played back
(BT3_PAD_PLAY, source/port/src/plat_stub.c), from the boot to the end of a fight, through the real menus.

The game reads both pads once per game frame (18 bytes each: two button bytes, active low, then the right and
left sticks); a "tick" here is one such pair of reads. Reads stop while the game loads, so a script counted in
ticks replays the same way every time, given the same save (a fixed copy in tools/testsave).
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from bt3mod import game, modpack  # noqa: E402

BUTTONS = {"select": 0x0001, "l3": 0x0002, "r3": 0x0004, "start": 0x0008, "up": 0x0010, "right": 0x0020,
           "down": 0x0040, "left": 0x0080, "l2": 0x0100, "r2": 0x0200, "l1": 0x0400, "r1": 0x0800,
           "triangle": 0x1000, "circle": 0x2000, "cross": 0x4000, "square": 0x8000}
TESTSAVE = os.path.join(HERE, "testsave")


def _pad(btn=0, lx=0x80, ly=0x80):
    data = bytearray(18)
    data[0] = ~btn & 0xFF
    data[1] = ~(btn >> 8) & 0xFF
    data[2] = data[3] = 0x80
    data[4], data[5] = lx, ly
    return bytes(data)


IDLE = _pad()


class Script:
    """Player 1's input, tick by tick. Player 2's pad stays idle (the computer plays it in a fight)."""

    def __init__(self):
        self.ticks = []  # one (p1 bytes, p2 bytes) per tick
        self.marks = {}

    def wait(self, n):
        self.ticks += [(IDLE, IDLE)] * n
        return self

    def hold(self, buttons="", n=1, stick=None, player=1):
        btn = 0
        for b in buttons.split("+") if buttons else []:
            btn |= BUTTONS[b]
        lx, ly = {"up": (0x80, 0), "down": (0x80, 0xFF), "left": (0, 0x80), "right": (0xFF, 0x80),
                  None: (0x80, 0x80)}[stick]
        pad = _pad(btn, lx, ly)
        self.ticks += [(pad, IDLE) if player == 1 else (IDLE, pad)] * n
        return self

    def press(self, buttons, n=4, gap=10, player=1):
        """A short press, then a pause so the menus see one press."""
        return self.hold(buttons, n, player=player).wait(gap)

    def mark(self, name):
        self.marks[name] = len(self.ticks)
        return self

    def bytes(self):
        # Player 2's last four pressure bytes (never read by the game: src/sys/pad.c) carry the tick number, so the
        # per-vertical-blank table of the run (BT3_PAD_TABLE) says which tick the game read when.
        out = bytearray()
        for i, (a, b) in enumerate(self.ticks):
            out += a + b[:14] + (i + 1).to_bytes(4, "little")
        return bytes(out)


def to_duel(s, confirms=10):
    """From the boot to a 1P vs COM single battle with the select screens' default picks (with the test save:
    Goku (Early) against Kid Gohan, Wasteland - Noon). Found by looking at screenshots of each step."""
    # "Press START button" -> New Game / Continue. START is pressed again and again: the moment the title takes it
    # moves from release to release, and on the next menu START does nothing.
    s.wait(2300)
    for _ in range(10):
        s.press("start", 6, 54)
    s.wait(100)
    s.press("cross", 4, 200)                             # New Game
    s.press("cross", 4, 150)                             # create a save file? -> No
    s.press("left", 6, 60).press("cross", 4, 400)        # start without saving? -> Yes -> main menu
    s.press("down", 4, 100).press("down", 4, 100).press("down", 4, 100).press("cross", 4, 250)  # Duel
    for _ in range(confirms):                            # 1P vs COM, Single Battle, characters, map ...
        s.press("cross", 4, 150)
    return s.mark("menus done")


FIGHT_TICK = 6500  # with to_versus: "Fight!" is over and both fighters can act (the fight state starts at 5924)


def to_versus(s):
    """From the boot to a 1P vs 2P single battle where player 2 never touches the pad: a passive opponent, so
    what player 1 does can be measured. Goku (Early) against Kid Gohan, Wasteland - Noon, split screen.
    After it, s is at FIGHT_TICK."""
    # "Press START button" -> New Game / Continue. START is pressed again and again: the moment the title takes it
    # moves from release to release, and on the next menu START does nothing.
    s.wait(2300)
    for _ in range(10):
        s.press("start", 6, 54)
    s.wait(100)
    s.press("cross", 4, 200)                             # New Game
    s.press("cross", 4, 150)                             # create a save file? -> No
    s.press("left", 6, 60).press("cross", 4, 400)        # start without saving? -> Yes -> main menu
    s.press("down", 4, 100).press("down", 4, 100).press("down", 4, 100).press("cross", 4, 250)  # Duel
    s.press("down", 4, 40).press("cross", 4, 150)        # 1P VS 2P
    s.press("cross", 4, 150)                             # Single Battle
    for _ in range(3):                                   # player 1: character, Normal, colour 1
        s.press("cross", 4, 150)
    for _ in range(3):                                   # player 2: the same
        s.press("cross", 4, 150, player=2)
    for _ in range(3):                                   # map, music, start
        s.press("cross", 4, 150)
    s.wait(FIGHT_TICK - len(s.ticks))
    return s.mark("fight")


def run(script, out, pack=None, shots=0, first=None, last=None, seconds=120, trace=10):
    """Applies `pack` (a pack dict, a pack file, or None for the original game), plays the script and returns
    the health changes of the fight as [(vblank, (hp side 0, hp side 1))]."""
    import kit  # the test game (testkit/): its own gamedata and mods; the player's game is never touched
    g = game.Game(kit.DATA)
    if pack is None:
        g.remove()
    else:
        g.apply(modpack.load(pack) if isinstance(pack, str) else pack)
    exe = kit.EXE
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "port", "build", "shots"))
    shutil.copytree(TESTSAVE, os.path.join(out, "saves"))  # the run's own copy: a run may save
    with open(os.path.join(out, "input.pad"), "wb") as f:
        f.write(script.bytes())
    env = dict(os.environ, BT3_DATA=g.root, BT3_SAVES=os.path.join(out, "saves"), BT3_PAD_PLAY="input.pad",
               BT3_PAD_TABLE="table.pad", BT3_NOSOUND="1", BT3_HASH="hash.txt", BT3_NOMOVIE="1")
    if shots:
        env["BT3_SHOT"] = str(shots)
        if first is not None:
            env["BT3_SHOT_FROM"] = str(first)
        if last is not None:
            env["BT3_SHOT_TO"] = str(last)
    with open(os.path.join(out, "out.txt"), "w") as so, open(os.path.join(out, "err.txt"), "w") as se:
        try:
            subprocess.run([exe], cwd=out, env=env, stdout=so, stderr=se, timeout=seconds)
        except subprocess.TimeoutExpired:
            pass
    return fight_log(out)


def fight_log(out):
    """Health changes of the fight from the run's state log (BT3_HASH, source/port/src/gs/state.c: one line per
    vertical blank, with the fighters' health during a fight and how far the input file has been read):
    [(tick, (hp side 0, hp side 1))], tick = the script tick the game was at."""
    events, prev = [], None
    path = os.path.join(out, "hash.txt")
    if not os.path.exists(path):
        return events
    for line in open(path):
        w = line.split()
        if "hp" not in w or not line.endswith("\n"):  # (the last line may be cut where the run was stopped)
            continue
        i = w.index("hp")
        try:
            hp = (int(w[i + 1]), int(w[i + 2]))
            tick = int(w[w.index("pad") + 1]) // 36 if "pad" in w else -1
        except (IndexError, ValueError):
            continue
        if hp != prev:
            events.append((tick, hp))
            prev = hp
    return events


def ticks_by_vblank(out):
    """For every vertical blank of the run, the tick the game had read last (0 = none yet)."""
    data = open(os.path.join(out, "table.pad"), "rb").read()
    return [int.from_bytes(data[i + 18 + 14:i + 36], "little") for i in range(0, len(data) - 35, 36)]


def shots(out):
    d = os.path.join(out, "port", "build", "shots")
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".ppm"))
