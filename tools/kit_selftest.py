"""Self-test of the test kit and of the mod engine: replays every check made so far and compares with the expected
results. Usage:
    py -I tools/kit_selftest.py          after a change to bt3mod or the tools (~1 min)
    py -I tools/kit_selftest.py --full   after a change to the test program (testkit-src): adds the crash check,
                                         which costs a restart of the game, and the character select check
Needs the test game (started here in battles mode if needed). Leaves the test game without mods."""
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import kit  # noqa: E402
from bt3mod import modpack  # noqa: E402

TMP = tempfile.mkdtemp(prefix="bt3kit_")
GOKU, GOHAN = 0, 11
RESULTS = []
FULL_KI = {"roster.kiStart": 100000}  # (the Kamehameha costs 60000; no idle wait: see MACROS in kit.py)
MAX_POWER = dict(FULL_KI, **{"param.blastGain": 1000000, "param.maxPowerChargeTime": 0.5, "param.maxPowerTime": 60})
GRAFT = [{"slot": 2, "from": 33, "fromSlot": 2}]  # Super Vegeta's Final Flash as Goku (Early)'s Ultimate
MELEE = ["hold 3 cross", "hold 40 cross", "hold 6 -"] + ["hold 3 square", "hold 8 -"] * 8


def pack(name, chars):
    """A pack file: chars = {character id: {"fields": .., "transplants": .., "base": ..}}."""
    p = modpack.new(name)
    for c, ch in chars.items():
        modpack.chara(p, c).update(ch)
    path = os.path.join(TMP, name + ".json")
    modpack.save(p, path)
    return path


def setup(pack_path=None, mode=6, p0=GOKU):
    if pack_path != "keep":
        kit.apply(pack_path or "--none")
    ans = kit.send([f"fight {p0} 0 {GOHAN} 0 0 {-1 if mode == 6 else -2} {mode}"])
    assert ans.startswith("fight"), ans


def play(inputs, after=400):
    """Plays inputs fast from a fresh rematch: (hits on P1, actions of P0, animations of P0, final state)."""
    ans = kit.send(kit.expand(["speed fast", "restart", "log"] + inputs + ["sync", f"wait {after}", "log", "speed normal",
                                                                         "state"]))
    lines = ans.splitlines()
    hits = [int(l.split()[3].split("=")[1]) for l in lines if l.startswith("hit") and " p1 " in l]
    acts = [l.split()[3] for l in lines if l.startswith("action") and " p0 " in l]
    anims = [l.split()[3] for l in lines if l.startswith("anim") and " p0 " in l]
    st = kit.parse_state([l for l in lines if l.startswith("state")][-1])
    return hits, acts, anims, st


def check(name, ok, detail, t0):
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name:44} {detail}  ({time.time() - t0:.1f} s)", flush=True)


def near(a, b, tol=0.03):
    return b != 0 and abs(a - b) <= abs(b) * tol


def main(full):
    t_all = time.time()
    kit.ensure()  # (in battles mode: a test game left in menus mode is started again)

    # the reference: the same Kamehameha twice gives the same hits
    t = time.time()
    setup(pack("fullki", {GOKU: {"fields": FULL_KI}}))
    a, _, _, _ = play(["blast2a"])
    b, _, _, _ = play(["blast2a"])
    base_k = sum(a)
    check("determinism (Kamehameha twice)", a == b and base_k > 0, f"{a} / {b}", t)

    # one pack, two checks: technique damage x2 and the shared character table (health, starting ki)
    t = time.time()
    setup(pack("kame2", {GOKU: {"fields": {"super.damage.0": 6730 * 2, "roster.health": 70000, "roster.kiStart": 100000}}}))
    st = kit.parse_state(kit.send(["state"]).strip())
    check("health 7 bars, ki full at start", st["p0"]["hp"] == "70000/70000" and int(st["p0"]["ki"]) >= 99000,
          f"hp {st['p0']['hp']} ki {st['p0']['ki']}", t)
    k2, _, _, _ = play(["blast2a"])
    check("Kamehameha damage x2", near(sum(k2), 2 * base_k), f"{base_k} -> {sum(k2)}", t)

    t = time.time()
    setup()
    m1, _, _, _ = play(MELEE, 120)
    setup(pack("melee3", {GOKU: {"fields": {"melee.damageScale": 300}}}))
    m3, _, _, _ = play(MELEE, 120)
    ok = len(m1) == len(m3) and len(m1) > 0 and all(near(y, 3 * x, 0.05) for x, y in zip(m1, m3))
    check("melee damage x3", ok, f"{sum(m1)} -> {sum(m3)} ({len(m1)} hits)", t)

    # a whole technique moved between characters, three packs in a row without restarting (the last one = the
    # first: nothing of a replaced pack stays); its animations seen by the game (start pose 0x16B, block 0x149..)
    ff = {}
    for dmg, expect in ((11110, 12240), (22220, 24480), (11110, 12240)):
        t = time.time()
        ff[dmg] = pack(f"ff{dmg}", {GOKU: {"fields": dict(MAX_POWER, **{"super.damage.2": dmg}), "transplants": GRAFT}})
        setup(ff[dmg])
        h, acts, anims, _ = play(["ultimate"])
        ok = sum(h) == expect and "0x105" in acts and "0x16B" in anims and "0x149" in anims
        check(f"Final Flash graft, damage {dmg} (+anims)", ok, f"{len(h)} hits = {sum(h)}", t)

    # the same pack (still applied), a real versus battle: no refill of health
    t = time.time()
    setup("keep", mode=0)
    h, _, _, st = play(["ultimate"])
    check("versus mode (no refill), same damage", sum(h) == 12240 and st["p1"]["hp"].startswith(str(30000 - 12240)),
          f"{sum(h)}, P1 hp {st['p1']['hp']}", t)

    # snapshots: the same Ultimate three times from one saved moment, the same hits every time
    t = time.time()
    setup("keep")
    kit.send(kit.expand(["speed fast", "maxpower", "sync", "speed normal"]))
    runs = []
    ult = ["log", "hold 8 l2+down", "hold 10 l2+triangle+down", "hold 6 l2+down", "speed fast", "sync", "wait 400",
           "speed normal", "log"]
    for i in range(3):  # (the snapshot and the inputs in one mailbox: they start at the same moment of the game)
        ans = kit.send([("snap save 0" if i == 0 else "snap load 0")] + ult)
        runs.append([l for l in ans.splitlines() if l.startswith("hit")])
    check("snapshot: 3 replays identical (to the frame)", runs[0] and runs[0] == runs[1] == runs[2],
          f"{len(runs[0])} hits each", t)

    # screenshots: one, then a burst taken by the game
    t = time.time()
    png = os.path.join(TMP, "shot.png")
    kit.shot(png)
    res = kit.experiment(["hold 20 l2"], shots=6, shots_every=5, settle=0, fresh=False)
    sheet = res.get("sheet")
    ok = os.path.exists(png) and os.path.getsize(png) > 10000 and bool(sheet) and os.path.getsize(sheet) > 10000
    check("screenshot + burst + contact sheet", ok, "", t)

    # a slot replaced by a copy of another character: Pilaf Machine (152) <- Super Vegeta (33), same Blast 2
    t = time.time()
    clone = pack("clone", {152: {"base": 33, "fields": FULL_KI}, 33: {"fields": FULL_KI}})
    a = kit.experiment(["blast2a"], pack=clone, p0=33, p1=GOHAN)
    b = kit.experiment(["blast2a"], p0=152, p1=GOHAN)
    ha = [d for s, d in a.get("hits", []) if s == "p1"]
    hb = [d for s, d in b.get("hits", []) if s == "p1"]
    check("slot replaced by a copy (152 <- 33)", ha and ha == hb, f"{ha} / {hb}", t)

    # a technique that needs its character's own data (model motions, camera cut): Goku (End)'s Super Spirit Bomb
    # as the Ultimate of the Super Vegeta copy (crashed in DemoCam_SetAnim before the camera cut came along)
    t = time.time()
    ssb = pack("ssb", {152: {"base": 33, "fields": MAX_POWER, "transplants": [{"slot": 2, "from": 3, "fromSlot": 2}]},
                       GOHAN: {"fields": {"roster.health": 70000}}})
    r = kit.experiment(["ultimate"], pack=ssb, p0=152, p1=GOHAN, settle=900)
    h = [d for s, d in r.get("hits", []) if s == "p1"]
    check("graft with camera cut (Super Spirit Bomb)", len(h) == 18 and sum(h) == 16400,
          r.get("error", "")[:120] or f"{len(h)} hits = {sum(h)}", t)
    kit.ensure()

    # a Blast 1 moved between characters: Vegeta's Explosive Wave in place of Goku (Early)'s Solar Flare hits like
    # Vegeta's own (walk up to the opponent; hold charge, then press guard: Blast 1 n°1)
    t = time.time()
    skill_in = ["hold 70 - up", "hold 6 l2", "hold 6 l2+circle", "hold 6 -"]
    gain = {"param.blastGain": 1000000, "roster.kiStart": 100000}
    graft = pack("skill", {GOKU: {"fields": gain, "transplants": [{"kind": "skill", "slot": 0, "from": 31,
                                                                       "fromSlot": 0}]}, 31: {"fields": gain}})
    r1 = kit.experiment(skill_in, pack=graft, p0=GOKU, p1=GOHAN, settle=300)
    r2 = kit.experiment(skill_in, p0=31, p1=GOHAN, settle=300)
    h1 = [d for s, d in r1.get("hits", []) if s == "p1"]
    h2 = [d for s, d in r2.get("hits", []) if s == "p1"]
    check("Blast 1 graft (Explosive Wave)", h1 and h1 == h2 and ("p0", "0x103") in r1.get("anims", []),
          r1.get("error", "")[:120] or f"{h1} / Vegeta {h2}", t)

    # copies of a transformation chain: Vegeta (31) in 152, Super Vegeta (33) in 153. R3 + up turns the copy of
    # Vegeta into the copy of Super Vegeta, R3 + down back (the game takes a direction held when R3 is released,
    # and refuses a locked target: unlock); the Pilaf Machine cell of the grid offers the copies' forms
    t = time.time()
    chain = pack("chain", {152: {"base": 31, "fields": {"param.blastGain": 1000000}},
                           153: {"base": 33, "fields": {"param.blastGain": 1000000}}})
    kit.apply(chain)
    ans = kit.send(["unlock", f"fight 152 0 {GOHAN} 0", "speed fast", "hold 60 -", "hold 4 r3+up", "hold 4 up", "sync",
                    "wait 200", "state", "hold 4 r3+down", "hold 4 down", "sync", "wait 200", "speed normal", "state"])
    seen = [kit.parse_state(l)["p0"].get("chara") for l in ans.splitlines() if l.startswith("state")]
    from bt3mod import game as game_mod, menunames
    g = game_mod.Game(kit.DATA)
    cell = [c for c in menunames.read_grid(open(os.path.join(g.mods_dir, "00454.bin"), "rb").read()) if c[0] == 152]
    check("transformations between copies + grid forms", seen == ["153", "152"] and cell[0][1:5] == [3, 152, 32, 153],
          f"152 -> {' -> '.join(map(str, seen))}, cell {cell[0][2:2 + cell[0][1]]}", t)

    if full:
        # a crash: reported with the function's name, then the game comes back
        t = time.time()
        from bt3mod import game, pak
        g = game.Game(kit.DATA)
        kit.apply("--none")
        kit.send(["release"])
        names = []
        for idx, entries in g.costumes(GOKU):
            entries = list(entries)
            entries[17] = bytes(len(entries[17]))  # general parameters zeroed: a division by zero in the gauges
            open(os.path.join(g.mods_dir, "%05d.bin" % idx), "wb").write(pak.write(entries))
            names.append("%05d.bin" % idx)
        g._save_manifest({"files": names})
        ans = kit.send([f"fight {GOKU} 0 {GOHAN} 0"], timeout=60)
        crashed = ans.startswith("error: the test game stopped") and "BtlParam_GetMaxPowerDrain" in ans
        kit.apply("--none")
        kit.ensure()
        back = kit.send([f"fight {GOKU} 0 {GOHAN} 0"]).startswith("fight")
        check("crash reported (named) and recovered", crashed and back,
              "crash seen, restarted" if crashed and back else ans[:200], t)

        # the clone on the character select (the game's own menus)
        t = time.time()
        import menu_check
        menu_check.main(clone, ["down*12+right*2"], quiet=True)
        ok = menu_check.LAST_MENU == "39"
        check("character select reached (see menu_check.png)", ok, f"menu {menu_check.LAST_MENU}", t)
        kit.ensure()

    kit.apply("--none")
    kit.stop()  # (the test game is closed at the end: the next test starts it again)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed in {time.time() - t_all:.0f} s"
          + ("" if full else "  (--full adds the crash and character select checks)"))
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main("--full" in sys.argv))
