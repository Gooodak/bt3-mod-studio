"""The library of mods with REAL community mods (in testkit/community_mods, downloaded for testing only: never
shared), into a test library (testkit/library_test, never the person's), then in the TEST game:
  1. Turles - Super Saiyan (.7z): its two forms recognised by their names (slots 121, 122);
  2. an added character made from its Super Saiyan form, with the pack's changes on top (health, a grafted Ultimate,
     a renamed move): its own moves, the change seen in battle;
  3. the DBZL modpack: its new characters get a base character from their animations; Frost, added, fights.
    py -I tools/library_check.py          (about 2 minutes; skipped when the community mods are not there)"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import kit  # noqa: E402

os.environ["BT3MS_LIBRARY"] = os.path.join(kit.KIT, "library_test")
from bt3mod import game, library, modpack  # noqa: E402

MODS = os.path.join(kit.KIT, "community_mods")
TURLES = os.path.join(MODS, "turles", "turles_-_super_saiyan.7z")
DBZL = os.path.join(MODS, "dbzl", "dbzl_exclusives_modpack_-_volume_1_2.7z")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name:52} {detail}", flush=True)


def fight(path, chara):
    kit.stop()  # (the game reads its characters folder when it starts)
    kit.apply(path)
    kit.ensure()
    r = kit.experiment(["ultimate"], p0=chara, p1=11, settle=600)
    st = r.get("state", {}).get("p0", {})
    return st, [d for s, d in r.get("hits", []) if s == "p1"]


def main():
    sys.stdout.reconfigure(errors="replace")
    if not (os.path.exists(TURLES) and os.path.exists(DBZL)):
        print("SKIP  the community mods are not in testkit/community_mods")
        return 0
    shutil.rmtree(os.environ["BT3MS_LIBRARY"], ignore_errors=True)
    g = game.Game(kit.DATA)
    r = library.import_mod(g, TURLES)
    by = {e["group"]: e for e in r["entries"]}
    check("Turles: two forms, by their slot names", set(by) == {"Turles_0", "Turles_1"} and
          by["Turles_1"]["slot"] == 122 and by["Turles_0"]["slot"] == 121, str({k: v["slot"] for k, v in by.items()}))

    ssj = by["Turles_1"]["id"]
    pack = modpack.new("Test bibliothèque", "library_check")
    e = modpack.add(pack, by["Turles_1"]["base"], "Turles SSJ")
    e["mod"] = ssj
    e["fields"]["roster.health"] = 60000
    e["fields"]["roster.kiStart"] = 100000
    e["texts"] = {"en": {"4": "Test Blaster"}}
    names = g.start_move_names(122, {k: v for k, v in e.items() if k not in ("base", "name", "form")})
    check("its own moves (from the mod)", "Calamity Blaster" in [n.strip() for n in names] or
          "Test Blaster" in [n.strip() for n in names], ", ".join(n.strip() for n in names[:5]))
    files = g.build_added(e, pack)
    check("its package: the mod's files and character.txt", "chara_1p.pak" in files and "voice_us/000.adx" in files
          and "portrait.bin" in files and b"health=60000" in files["character.txt"], f"{len(files)} files")
    path = os.path.join(tempfile.mkdtemp(prefix="bt3lib_"), "lib.bt3mod.json")
    modpack.save(pack, path)
    st, hits = fight(path, 198)
    check("in the game: the mod's Turles, 60000 health, his Ultimate", st.get("chara") == "198" and
          st.get("hp", "").endswith("/60000") and len(hits) > 0, f"hp {st.get('hp')}, {len(hits)} hits = {sum(hits)}")

    r = library.import_mod(g, DBZL)
    frost = next(x for x in r["entries"] if x["group"] == "Frost")
    check("DBZL: new characters get a base from their animations", frost["slot"] is None and
          frost["base"] in (91, 92, 93, 94, 95, 96), f"Frost -> {frost['base']} ({frost['why']})")
    pack = modpack.new("Test Frost", "library_check")
    e = modpack.add(pack, frost["base"], "Frost")
    e["mod"] = frost["id"]
    e["fields"]["roster.kiStart"] = 100000
    modpack.save(pack, path)
    st, hits = fight(path, 198)
    check("in the game: Frost (DBZL) fights with his Ultimate", st.get("chara") == "198" and len(hits) > 0,
          f"hp {st.get('hp')}, {len(hits)} hits = {sum(hits)}")
    kit.apply("--none")
    kit.stop()
    shutil.rmtree(os.environ["BT3MS_LIBRARY"], ignore_errors=True)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
