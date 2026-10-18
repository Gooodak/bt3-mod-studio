"""Online play of BT3 Mod Studio's edition of the port: two copies of the TEST game on this PC, one hosting, one
joining over 127.0.0.1, each on its own data folder (the second is made of hard links to the first, with a mods
folder of its own). Checks:
  1. the same pack on both sides: they connect;
  2. a pack on one side only: refused as "another version or other mods";
  3. the official port (testkit/bt3-upstream.exe) against this edition: refused.
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
PORT = 47131
RESULTS = []


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


def run(exe, root, role, log, saves):
    shutil.rmtree(saves, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "testsave"), saves)
    env = dict(os.environ, BT3_DATA=root, BT3_SAVES=saves, BT3_NOSOUND="1", BT3_NOMOVIE="1", BT3_UPDATE_CHECK="0",
               BT3_NET_SESSION="1")
    env.pop("BT3_TEST", None)
    env["BT3_NET_HOST" if role == "host" else "BT3_NET_JOIN"] = str(PORT) if role == "host" else f"127.0.0.1:{PORT}"
    return subprocess.Popen([exe], cwd=kit.KIT, env=env, stdout=open(log, "w"), stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)


def match(host_exe, join_exe, seconds=45):
    """Starts the two copies; returns (connected?, host log, joiner log)."""
    tmp = tempfile.mkdtemp(prefix="bt3net_")
    logs = [os.path.join(tmp, "host.log"), os.path.join(tmp, "join.log")]
    procs = [run(host_exe, kit.DATA, "host", logs[0], os.path.join(tmp, "saves_h"))]
    time.sleep(1.0)
    procs.append(run(join_exe, DATA_B, "join", logs[1], os.path.join(tmp, "saves_j")))
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


def main():
    sys.stdout.reconfigure(errors="replace")
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
    for name in ("bt3.exe", "bt3-upstream.exe"):  # (the test programs only; the player's game has another name)
        subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
