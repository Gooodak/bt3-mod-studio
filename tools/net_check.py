"""Online play of BT3 Mod Studio's edition of the port: two copies of the TEST game on this PC, one hosting, one
joining over 127.0.0.1, each on its own data folder (the second is made of hard links to the first, with a mods
folder of its own). Checks:
  1. the same pack on both sides: they connect;
  2. a pack on one side only: refused as "another version or other mods";
  3. the official port (testkit/bt3-upstream.exe) against this edition: refused;
  4. the same added character package (a copy of Vegeta, made by z3xox's import_chara.py) on both: they connect,
     both with the package loaded;
  5. different packages: refused.
    py -I tools/net_check.py          (about 1 to 2 minutes; the player's own game is never touched)"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import kit  # noqa: E402
from bt3mod import game, modpack  # noqa: E402

DATA_B = os.path.join(kit.KIT, "gamedata_b")
IMPORT = os.path.join(os.path.dirname(kit.KIT), "source", "port", "tools", "import_chara.py")
PORT = 47131
RESULTS = []
NONE = os.path.join(kit.KIT, "chars_none")


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name:52} {detail}", flush=True)


def second_root():
    """testkit/gamedata_b: hard links to every file of testkit/gamedata but its mods (made once)."""
    if os.path.isdir(os.path.join(DATA_B, "pzs3us1")):
        return
    t = time.time()
    for top, dirs, files in os.walk(kit.DATA):
        rel = os.path.relpath(top, kit.DATA)
        if rel == "." and "mods" in dirs:
            dirs.remove("mods")
        os.makedirs(os.path.join(DATA_B, rel), exist_ok=True)
        for f in files:
            if f.startswith(".fingerprint") or f == "bt3modstudio_manifest.json":
                continue
            dst = os.path.join(DATA_B, rel, f)
            if not os.path.exists(dst):
                os.link(os.path.join(top, f), dst)
    print(f"(second data folder made of hard links in {time.time() - t:.0f} s)")


def set_pack(root, pack):
    g = game.Game(root)
    g.remove()
    if pack is not None:
        g.apply(pack)


def packages():
    """testkit/chars_a and chars_b: the same package (Vegeta added); chars_c: another (Goku Early added)."""
    folders = {}
    for name, chara, label in (("chars_a", 31, "Vegeta Test"), ("chars_c", 0, "Goku Test")):
        d = os.path.join(kit.KIT, name)
        if not os.path.isdir(os.path.join(d, label)):
            os.makedirs(d, exist_ok=True)
            subprocess.run([sys.executable, "-I", IMPORT, kit.DATA, str(chara), os.path.join(d, label), "--name", label],
                           check=True, capture_output=True)
        folders[name] = d
    b = os.path.join(kit.KIT, "chars_b")
    shutil.rmtree(b, ignore_errors=True)
    shutil.copytree(folders["chars_a"], b)
    folders["chars_b"] = b
    empty = os.path.join(kit.KIT, "chars_none")
    os.makedirs(empty, exist_ok=True)
    folders["none"] = empty
    return folders


def press_table(path, blanks, seed=1):
    """BT3_NET_SCRIPT's table: 36 bytes per blank (pad 1, pad 2), the PS2 pad's 18 bytes each (buttons active-low,
    sticks at 0x80, then the pressures). Random buttons held a few blanks each; never Select, Start or Triangle
    (the pause and "back" would leave the fight)."""
    import random
    rnd = random.Random(seed)
    usable = [(0, 4), (0, 5), (0, 6), (0, 7), (1, 0), (1, 1), (1, 2), (1, 3), (1, 6), (1, 7)]  # (no circle either)
    out = bytearray()
    state = [None, None]
    for blank in range(blanks):
        for pad in range(2):
            if blank < 3600:  # (the session starts at the character select near blank 2009: only cross until
                # the fight is on, so that the menus are only ever confirmed: a random press there could take the
                # game back to the main menu, which ends a session; the host's random seed decides the menus' path)
                b = [0xFF, 0xFF & ~(1 << 6)] if blank % 30 < 6 else [0xFF, 0xFF]
                out += bytes(b) + bytes([0x80] * 4) + bytes(0xFF if (k < 8 and b[1] != 0xFF) else 0 for k in range(12))
                continue
            if state[pad] is None or state[pad][0] <= blank:
                held = rnd.sample(usable, rnd.choice((0, 1, 1, 2)))
                if rnd.random() < 0.35:
                    held.append((1, 6))  # (cross often: the selects go on)
                state[pad] = (blank + rnd.randint(4, 20), held, [rnd.choice((0x00, 0x80, 0xFF)) for _ in range(4)])
            _, held, sticks = state[pad]
            b = [0xFF, 0xFF]
            for byte, bit in held:
                b[byte] &= ~(1 << bit)
            out += bytes(b) + bytes(sticks) + bytes(0xFF if (k < 8 and b[1] != 0xFF) else 0 for k in range(12))
    open(path, "wb").write(bytes(out))


def fight(chars, seconds=150, seed=1):
    """Both copies in a session, windowless, playing one table of random presses, both fighters the added
    character: did a battle start, and did the two games stay the same (the netcode compares them itself)?"""
    tmp = tempfile.mkdtemp(prefix="bt3fight_")
    table = os.path.join(tmp, "presses.bin")
    press_table(table, 60 * 600, seed)
    logs = [os.path.join(tmp, "host.log"), os.path.join(tmp, "join.log")]
    hashes = [os.path.join(tmp, "host_hash.txt"), os.path.join(tmp, "join_hash.txt")]
    extra = dict(BT3_GS="none", BT3_NET_SCRIPT=table, BT3_TEST_CHARA="0xC6,0xC6", BT3_CHARA_LOG="1")
    procs = [run(kit.EXE, kit.DATA, "host", logs[0], os.path.join(tmp, "saves_h"), chars[0],
                 dict(extra, BT3_HASH=hashes[0]))]
    time.sleep(1.0)
    procs.append(run(kit.EXE, DATA_B, "join", logs[1], os.path.join(tmp, "saves_j"), chars[1],
                     dict(extra, BT3_HASH=hashes[1])))
    end = time.time() + seconds
    while time.time() < end and all(p.poll() is None for p in procs):
        time.sleep(1.0)
    for p in procs:
        if p.poll() is None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    time.sleep(1.0)
    fights = []
    for f in hashes:  # blank -> (fight values' hash, health), the last line of a blank counting (rollback)
        rows = {}
        for line in open(f, errors="replace") if os.path.exists(f) else []:
            w = line.split()
            if len(w) >= 6 and w[2] != "0000000000000000" and w[3] == "hp":
                rows[int(w[0])] = (w[2], int(w[4]), int(w[5]))
        fights.append(rows)
    return [open(f, errors="replace").read() for f in logs], fights, tmp


def run(exe, root, role, log, saves, chars, extra=None):
    shutil.rmtree(saves, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "testsave"), saves)
    env = dict(os.environ, BT3_DATA=root, BT3_SAVES=saves, BT3_NOSOUND="1", BT3_NOMOVIE="1", BT3_UPDATE_CHECK="0",
               BT3_NET_SESSION="1", BT3_CHARACTERS=chars, BT3_GS="none")  # (no window)
    env.update(extra or {})
    env.pop("BT3_TEST", None)
    env["BT3_NET_HOST" if role == "host" else "BT3_NET_JOIN"] = str(PORT) if role == "host" else f"127.0.0.1:{PORT}"
    return subprocess.Popen([exe], cwd=kit.KIT, env=env, stdout=open(log, "w"), stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)


def match(host_exe, join_exe, chars=None, seconds=45):
    """Starts the two copies; returns (connected?, host log, joiner log)."""
    tmp = tempfile.mkdtemp(prefix="bt3net_")
    logs = [os.path.join(tmp, "host.log"), os.path.join(tmp, "join.log")]
    chars = chars or (NONE, NONE)
    procs = [run(host_exe, kit.DATA, "host", logs[0], os.path.join(tmp, "saves_h"), chars[0])]
    time.sleep(1.0)
    procs.append(run(join_exe, DATA_B, "join", logs[1], os.path.join(tmp, "saves_j"), chars[1]))
    end = time.time() + seconds

    def read():
        return [open(f, errors="replace").read() for f in logs]
    try:
        while time.time() < end:
            time.sleep(0.5)
            text = read()
            if all("bt3: net: connected" in t for t in text) or "other mods" in text[1] or \
                    any(p.poll() is not None for p in procs):
                time.sleep(1.0)
                break
    finally:
        for p in procs:
            if p.poll() is None:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        time.sleep(1.0)
    text = read()  # (what a copy writes may only reach the file when it ends)
    return all("bt3: net: connected" in t for t in text), text


def lines(text, *keys):
    return " | ".join(l.strip()[10:110] for l in text.splitlines() if any(k in l for k in keys))[:220]


def fight_check():
    """What is checked is that an online fight stays the same on both games. Reaching the fight goes through the
    menus with presses, and the host's random seed (drawn at each session) changes their path: now and then the
    session goes back to the main menu before any fight (no difference: both games do it at the same blank). So up
    to three tries, each with another table, to see a fight; a difference fails at once, no fight in three fails."""
    pk = packages()
    for attempt in (1, 2, 3):
        text, fights, tmp = fight((pk["chars_a"], pk["chars_b"]), seed=attempt)
        battles = [t.count("a battle is set up") for t in text]
        differ = [l for t in text for l in t.splitlines() if "the two games differ" in l]
        own = all("Vegeta Test_1p.pak" in t for t in text)  # (BT3_CHARA_LOG: the package's model was served)
        both = sorted(set(fights[0]) & set(fights[1]))
        unequal = [b for b in both if fights[0][b] != fights[1][b]]
        hits = len({fights[0][b][1:] for b in both})  # (different health pairs: the fighters hit each other)
        if differ or unequal or len(both) > 600:
            break
        print(f"      (try {attempt}: the session went back to the menus before a fight; another table)", flush=True)
    check("online fight with the added character: the same on both",
          min(battles) > 0 and not differ and len(both) > 600 and not unequal and hits > 2 and own,
          f"{len(both)} fight blanks compared, {len(unequal)} differ, {hits} health states, added character "
          f"{'served' if own else 'NOT seen'}, try {attempt}{', ' + differ[0][10:90] if differ else ''}  (logs: {tmp})")


def main():
    sys.stdout.reconfigure(errors="replace")
    os.makedirs(NONE, exist_ok=True)
    if "--fight" in sys.argv:
        kit.stop(quiet=True)
        second_root()
        fight_check()
        print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed")
        return 0 if all(RESULTS) else 1
    kit.stop(quiet=True)
    second_root()
    ours, official = kit.EXE, os.path.join(kit.KIT, "bt3-upstream.exe")
    pack = modpack.new("Test en ligne", "net_check")
    modpack.chara(pack, 0)["fields"]["roster.health"] = 60000

    set_pack(kit.DATA, pack)
    set_pack(DATA_B, pack)
    ok, text = match(ours, ours)
    check("same pack on both sides: they connect", ok, lines(text[1], "same data only", "connected", "other mods"))

    set_pack(DATA_B, None)
    ok, text = match(ours, ours)
    refused = "other mods" in text[1] or "another version" in text[1]
    check("pack on one side only: refused", not ok and refused, lines(text[1], "same data only", "other mods",
                                                                       "another version", "connected"))
    if os.path.exists(official):
        set_pack(kit.DATA, None)
        ok, text = match(ours, official)
        check("official port against this edition: refused", not ok,
              lines(text[1], "another version", "other mods", "connected"))
    set_pack(kit.DATA, None)
    set_pack(DATA_B, None)
    pk = packages()
    ok, text = match(ours, ours, (pk["chars_a"], pk["chars_b"]))
    loaded = all("characters: 1 added" in t for t in text)
    check("same added character on both sides: they connect", ok and loaded,
          lines(text[1], "characters: 1 added", "connected", "other mods"))
    ok, text = match(ours, ours, (pk["chars_a"], pk["chars_c"]))
    check("different character packages: refused", not ok and "other mods" in text[1],
          lines(text[1], "characters: 1 added", "other mods", "connected"))
    fight_check()
    for name in ("bt3.exe", "bt3-upstream.exe"):  # (the test programs only; the player's game has another name)
        subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
