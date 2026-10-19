"""Updates (bt3mod/updates.py) on a FAKE game folder and a copy of the tool, never the player's own game:
the extended edition's release read from GitHub, installed over an official game (the official program kept),
seen as up to date, and the official one put back; the tool's new version copying itself over a copy of the tool.
    py -I tools/update_check.py          (about 1 minute; needs the network)
While the repositories are private, GitHub answers only with a token: the one of the `gh` program is used."""
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
from bt3mod import game, updates  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name:52} {detail}", flush=True)


def main():
    sys.stdout.reconfigure(errors="replace")
    if not updates._token():
        gh = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "gh", "bin", "gh.exe")
        r = subprocess.run([gh, "auth", "token"], capture_output=True, text=True)
        if r.returncode == 0:
            os.environ["BT3MS_GITHUB_TOKEN"] = r.stdout.strip()
    tmp = tempfile.mkdtemp(prefix="bt3upd_")
    try:
        rel = updates.latest(updates.PORT_REPO)
        asset = updates.pick(rel["assets"], r"windows.*\.zip$")
        check("the extended edition's newest release", rel["tag"].startswith("v0.1.") and asset,
              f"{rel['tag']}, {asset['name'] if asset else 'no zip'}")

        # a fake game folder with the official program (the test kit's copy of z3xox's build)
        gdir = os.path.join(tmp, "Tenkaichi3Decomp")
        os.makedirs(os.path.join(gdir, "gamedata"))
        shutil.copy2(os.path.join(kit.KIT, "bt3-upstream.exe"), os.path.join(gdir, "Tenkaichi3Decomp.exe"))
        g = game.Game(os.path.join(gdir, "gamedata"))
        before = g.edition()
        upd, why = updates.game_update(g)
        zpath = os.path.join(tmp, asset["name"])
        updates.download(asset, zpath)
        n = updates.install_game(g, zpath, "etendu", rel["tag"])
        kept = os.path.exists(os.path.join(gdir, "Tenkaichi3Decomp-officielle.exe"))
        check("official -> extended: downloaded and installed", before == "officielle" and upd is not None and
              g.edition() == "etendu" and kept and updates.installed(g).get("tag") == rel["tag"],
              f"{before} -> {g.edition()}, {n} files, official kept: {kept} ({why})")
        upd2, why2 = updates.game_update(g)
        check("then up to date", upd2 is None, why2)
        updates.back_to_official(g)
        check("back to the official program", g.edition() == "officielle")

        # z3xox's own newest release, installed: then known exactly, and up to date
        o = updates.official_status(g)
        oasset = updates.pick(o["latest"]["assets"], r"windows.*\.zip$")
        opath = os.path.join(tmp, "official.zip")
        updates.download(oasset, opath)
        updates.install_game(g, opath, "officielle", o["latest"]["tag"])
        o2 = updates.official_status(g)
        check("z3xox's release installed, then up to date", g.edition() == "officielle" and o2["exact"] and
              o2["have"] == o["latest"]["tag"] and not o2["update"],
              f"{o['latest']['tag']}: had {o['have']} (guessed), now {o2['have']} (exact {o2['exact']})")

        # the tool: the release zip (build it first: tools/release_tool.py) staged, and its program, started the way
        # the tool starts it, copies itself over a copy of the tool once a fake "old tool" has closed (no restart)
        tdir = os.path.join(tmp, "tool")
        os.makedirs(tdir)
        with open(os.path.join(tdir, "BT3 Mod Studio.exe"), "wb") as f:
            f.write(b"old")
        tzip = os.path.join(os.path.dirname(kit.KIT), "releases", "BT3-Mod-Studio-windows.zip")
        new_exe = updates.stage_tool(tzip)
        old = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(4)"])
        updates.run_staged(new_exe, tdir, old.pid, restart=False)
        log = os.path.join(os.path.dirname(os.path.dirname(new_exe)), "update.log")
        early = os.path.getsize(os.path.join(tdir, "BT3 Mod Studio.exe"))
        for _ in range(120):
            if os.path.exists(log) and "mise à jour faite" in open(log, encoding="utf-8").read():
                break
            time.sleep(0.5)
        size = os.path.getsize(os.path.join(tdir, "BT3 Mod Studio.exe"))
        text = open(log, encoding="utf-8").read().strip().splitlines()[-1] if os.path.exists(log) else "no log"
        check("the tool's new version copies itself after the old closed", early == 3 and old.poll() is not None and
              size > 1000 and os.path.isdir(os.path.join(tdir, "runtime")), f"exe {size} bytes; {text}")
        shutil.rmtree(os.path.dirname(os.path.dirname(new_exe)), ignore_errors=True)
    except updates.UpdateError as e:
        check("GitHub reached", False, str(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
