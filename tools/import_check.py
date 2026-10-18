"""Importing a character mod (bt3mod/importer.py) into the TEST game, then fighting with it.
The mod is made here from the test game's own Vegeta files, named as the community passes them around
("Vegeta model(1733).unk"...), so nothing has to be downloaded. Also: a mod that is a package already, a zip.
    py -I tools/import_check.py          (about 1 minute; the player's own game is never touched)"""
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import kit  # noqa: E402
from bt3mod import game, importer  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name:52} {detail}", flush=True)


def loose_mod(folder):
    """Vegeta (31) as loose files with the archive's numbers in their names (counted from 0)."""
    os.makedirs(folder)
    g = game.Game(kit.DATA)
    first = game.CHARA_FIRST + 31 * 10
    for idx, label in ((first, "model"), (first + 1, "model"), (first + 4, "model dmg"), (first + 8, "anim"),
                       (first + 9, "effects"), (game.VOICE_BANK_ALT - 1 + 31, "voice"), (game.FACE_FILE - 1 + 31, "pic")):
        with open(os.path.join(folder, f"Vegeta {label}({idx}).unk"), "wb") as f:
            f.write(g.original(idx))


def main():
    sys.stdout.reconfigure(errors="replace")
    kit.stop()  # (the game reads its characters folder when it starts)
    g = game.Game(kit.DATA)
    tmp = tempfile.mkdtemp(prefix="bt3imp_")
    for p in importer.installed(g):  # (a test left behind by an earlier run)
        if not p["ours"] and p["folder"].startswith("Test "):
            importer.remove(g, p["folder"])
    try:
        src = os.path.join(tmp, "Vegeta mod")
        loose_mod(src)
        r = importer.import_mod(g, src, "Test Vegeta")
        want = {"chara_1p.pak", "chara_2p.pak", "chara_1p_dmg.pak", "chara_anm.pak", "chara_eff.pak",
                "chara_voice_us.pak", "portrait.bin", "character.txt"}
        check("loose files: recognised by their numbers", set(r["files"]) == want and r["base"] == 31,
              f"{sorted(r['files'])}, base {r['base']} ({r['why']})")

        # the same mod again, as a package in a zip: copied as it is
        pkg = os.path.join(game.Game(kit.DATA).characters_dir(), "Test Vegeta")
        z = os.path.join(tmp, "Test Pack.zip")
        with zipfile.ZipFile(z, "w") as zf:
            for f in os.listdir(pkg):
                zf.write(os.path.join(pkg, f), "Test Pack/" + f)
        r2 = importer.import_mod(g, z)
        check("a package in a zip: copied as it is", r2["folder"] == "Test Pack" and "chara_1p.pak" in r2["files"],
              f"{r2['folder']}: {len(r2['files'])} files")
        mine = [p["folder"] for p in importer.installed(g) if not p["ours"]]
        check("listed as installed, with a mark", "Test Vegeta" in mine and "Test Pack" in mine and
              len(importer.mark(g)) == 9, f"{mine} {importer.mark(g)}")
        importer.remove(g, "Test Pack")

        # in the game: the first added character (198) is the imported Vegeta
        kit.ensure()
        res = kit.experiment(["ultimate"], p0=198, p1=11, settle=600)
        st = res.get("state", {}).get("p0", {})
        hits = [d for s, d in res.get("hits", []) if s == "p1"]
        check("in the game: the imported character fights", st.get("chara") == "198" and bool(st.get("hp")),
              f"chara {st.get('chara')}, hp {st.get('hp')}, {len(hits)} hits")
    finally:
        kit.stop()
        for p in importer.installed(g):
            if not p["ours"] and p["folder"].startswith("Test "):
                importer.remove(g, p["folder"])
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
