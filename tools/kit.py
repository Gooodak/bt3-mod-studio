"""Client of the test kit built into the test program (testkit/bt3.exe, port/src/testkit.c of the testkit branch).

The game is started once and keeps running; every call sends commands through the mailbox folder and prints the
answers. A crash or a hang is reported at once (crash report with function names from the map file).
    py -I tools/kit.py start | stop | kill
    py -I tools/kit.py try PACK|- P0 P1 "input,input,..." [SHOTS]   one whole experiment (apply, fight, play,
                                                                    measure, screenshot burst + contact sheet)
    py -I tools/kit.py send "fight 0 0 11 0" "ultimate" "sync" ...   raw commands (macros allowed)
    py -I tools/kit.py timeline SAMPLES EVERY cmd ...                state table while inputs play
    py -I tools/kit.py shot out.png [--full]
    py -I tools/kit.py apply pack.json | --none                      the test game's own gamedata/mods
Game commands (port/src/testkit.c): fight C0 K0 C1 K1 [stage cpu1 mode], restart, release, hold N BUTTONS [STICK]
[p2], sync, wait N, state, log, flag N [P], shot PATH, shots N EVERY PREFIX, snap save|load K, speed fast|normal,
quit. Self-test: tools/kit_selftest.py (run it after any change). The player's own game is never touched.
"""
import os
import struct
import subprocess
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from bt3mod import game, modpack  # noqa: E402

KIT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "testkit")
EXE = os.path.join(KIT, "bt3.exe")
DATA = os.path.join(KIT, "gamedata")
BOX = os.path.join(KIT, "mailbox")


def _pid():
    try:
        return int(open(os.path.join(BOX, "pid")).read())
    except (OSError, ValueError):
        return None


def running():
    """Whether the test game's process is alive (asked from Windows directly: cheap enough to poll)."""
    import ctypes
    pid = _pid()
    if pid is None:
        return False
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    return bool(ok) and code.value == 259  # STILL_ACTIVE


def start(quiet=False, menus=False, sound=False):
    """menus=True: the game's own menus run (BT3_TEST_MENUS), on a fresh copy of the test save (tools/testsave)."""
    if running():
        if not quiet:
            print("already running")
        return
    os.makedirs(BOX, exist_ok=True)
    for f in [os.path.join(BOX, n) for n in ("cmd", "cmd.tmp", "reply", "reply.tmp")] + [os.path.join(KIT, "bt3_crash.txt")]:
        try:
            os.remove(f)
        except OSError:
            pass
    env = dict(os.environ, BT3_TEST=BOX, BT3_DATA=DATA, BT3_UPDATE_CHECK="0")
    if not sound:
        env["BT3_NOSOUND"] = "1"
    if menus:
        import shutil
        saves = os.path.join(BOX, "saves")
        shutil.rmtree(saves, ignore_errors=True)
        shutil.copytree(os.path.join(os.path.dirname(os.path.abspath(__file__)), "testsave"), saves)
        env.update(BT3_TEST_MENUS="1", BT3_SAVES=saves, BT3_NOMOVIE="1")
    log = open(os.path.join(BOX, "game.log"), "w")
    p = subprocess.Popen([EXE], cwd=KIT, env=env, stdout=log, stderr=subprocess.STDOUT,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    open(os.path.join(BOX, "pid"), "w").write(str(p.pid))
    open(os.path.join(BOX, "mode"), "w").write("menus" if menus else "battles")
    # Ready when the start-up check of the data is over (until then it holds the mod files open) and the mailbox
    # answers.
    t = time.time()
    while time.time() - t < 90:
        try:
            if "gameplay data:" in open(os.path.join(BOX, "game.log"), errors="replace").read():
                break
        except OSError:
            pass
        if not running():
            break
        time.sleep(0.1)
    if running():
        send(["state"], timeout=60)
    if not quiet:
        print("started, pid", p.pid, "ready in %.1f s" % (time.time() - t))


def kill():
    pid = _pid()
    if pid is not None and running():
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)


def mode():
    try:
        return open(os.path.join(BOX, "mode")).read().strip()
    except OSError:
        return "battles"


def ensure(menus=False):
    """The test game running in the mode wanted (battles without menus, or the game's own menus): started when it
    is not running (after a crash, say), started again when it runs in the other mode."""
    if running() and mode() != ("menus" if menus else "battles"):
        kill()
        time.sleep(0.5)
    if not running():
        start(quiet=True, menus=menus, sound=menus)


_SYMBOLS = None


def symbol(addr):
    """The function of the test program that holds a code address (from the linker's map, testkit/bt3.exe.map)."""
    global _SYMBOLS
    import bisect
    import re
    if _SYMBOLS is None:
        _SYMBOLS = []
        try:
            for line in open(EXE + ".map", errors="replace"):
                m = re.match(r"^\s+0x([0-9a-f]{16})\s+([A-Za-z_]\w*)\s*$", line)
                if m:
                    _SYMBOLS.append((int(m.group(1), 16), m.group(2)))
        except OSError:
            pass
        _SYMBOLS.sort()
    i = bisect.bisect_right(_SYMBOLS, (addr, "\x7f")) - 1
    if i < 0:
        return None
    a, name = _SYMBOLS[i]
    return f"{name}+0x{addr - a:X}"


def problem_report(lines=25):
    """What the game left behind: its crash report (code addresses named), else the end of its log."""
    import re
    crash = os.path.join(KIT, "bt3_crash.txt")
    if os.path.exists(crash):
        text = open(crash, errors="replace").read().splitlines()[:lines]
        named = []
        for line in text:
            m = re.search(r"0x(00000000[0-9A-Fa-f]{8}) \(.*bt3\.exe \+", line) or re.search(r" at 0x(00000000[0-9A-Fa-f]{8}) ", line)
            if m and "bt3.exe" in line:
                s = symbol(int(m.group(1), 16))
                line += f"   <- {s}" if s else ""
            named.append(line)
        return "crash report (testkit/bt3_crash.txt):\n  " + "\n  ".join(named)
    try:
        log = open(os.path.join(BOX, "game.log"), errors="replace").read().splitlines()
    except OSError:
        log = []
    return "end of the game's log:\n  " + "\n  ".join(log[-lines:])


def send(commands, timeout=120):
    """Sends commands (list of lines) and returns the answer text. When the game dies or does not answer, the
    answer starts with "error:" and carries the crash report or the end of the game's log."""
    if not running():
        return "error: the test game is not running (tools/kit.py start)\n" + problem_report() + "\n"
    # A new battle or a rematch is set up at full speed (0.6 s instead of 6 s): the game computes the same frames,
    # it only stops waiting for the screen. The speed asked for before is back afterwards.
    fast, cmds = False, []
    for c in commands:
        if c.startswith("speed "):
            fast = c.split()[1] == "fast"
        if c.split()[:1] in (["fight"], ["restart"]) and not fast:
            cmds += ["speed fast", c, "speed normal"]
        else:
            cmds.append(c)
    commands = cmds
    tmp, cmd, rep = (os.path.join(BOX, n) for n in ("cmd.tmp", "cmd", "reply"))
    try:
        os.remove(rep)
    except OSError:
        pass
    with open(tmp, "w") as f:
        f.write("\n".join(commands) + "\n")
    os.replace(tmp, cmd)
    t = time.time()
    n = 0
    while time.time() - t < timeout:
        if os.path.exists(rep):
            time.sleep(0.01)
            text = open(rep).read()
            os.remove(rep)
            return text
        n += 1
        if n % 10 == 0 and not running():
            return "error: the test game stopped while carrying out the commands\n" + problem_report() + "\n"
        time.sleep(0.01)
    return ("error: no answer after %d s: the game may be stuck (tools/kit.py kill, then start)\n" % timeout +
            problem_report(10) + "\n")


def state():
    """The 'state' answer as a dict: {'seq':.., 'p0': {'hp':..}, 'p1': {...}}."""
    line = send(["state"]).strip()
    out = {}
    cur = out
    for w in line.split()[1:]:
        if w in ("p0", "p1"):
            cur = out.setdefault(w, {})
            continue
        k, _, v = w.partition("=")
        cur[k] = v
    return out


# Input sequences for player 1 with the default controls (charge = L2, blast = triangle). Learned the hard way:
# - action 0x43 is an IDLE pose both fighters take after a few seconds of standing still; inputs are ignored while
#   it plays (~150 blanks): never leave the fighter idle before an input that matters (no long "hold N -");
# - the Ultimate needs down (d-pad or stick), lock-on and the Max Power mode (charge with full ki and a stock);
# - a technique needs its ki: the training mode refills ki only slowly (test packs set roster.kiStart 100000).
MACROS = {
    "maxpower": ["hold 150 l2", "hold 120 -"],                       # charge until Max Power, wait the power-up
    "blast2a": ["hold 8 l2", "hold 10 l2+triangle", "hold 6 l2"],     # technique slot 2
    "blast2b": ["hold 8 l2+up", "hold 10 l2+triangle+up", "hold 6 l2+up"],  # technique slot 3
    "ultimate": ["hold 150 l2", "hold 120 -", "hold 8 l2+down", "hold 10 l2+triangle+down", "hold 6 l2+down"],
}


def expand(cmds):
    """Commands with macro names (MACROS) replaced by their input lines."""
    out = []
    for c in cmds:
        out += MACROS.get(c, [c])
    return out


def parse_state(line):
    out, cur = {}, None
    for w in line.split()[1:]:
        if w in ("p0", "p1"):
            cur = out.setdefault(w, {})
            continue
        k, _, v = w.partition("=")
        (cur if cur is not None else out)[k] = v
    return out


def timeline(inputs, samples=20, every=30, before=()):
    """Sends `before` commands and the input lines, then samples the state `samples` times, `every` vertical
    blanks apart. Returns [(answer lines that are not states), [state dicts]]."""
    cmds = expand(list(before) + list(inputs))
    for _ in range(samples):
        cmds += [f"wait {every}", "state"]
    other, states = [], []
    for line in send(cmds, timeout=60 + samples * every // 30).splitlines():
        (states.append(parse_state(line)) if line.startswith("state ") else other.append(line))
    return other, states


def show(states):
    prev = None
    for s in states:
        p0, p1 = s.get("p0", {}), s.get("p1", {})
        row = (f"vb {s.get('vblank'):>6}  P0 hp {p0.get('hp', '?'):>11} ki {p0.get('ki', '?'):>6} mp {p0.get('maxpower', '?'):>5}"
               f" act {p0.get('action', '?'):>5} lock {p0.get('lock', '?')} pow {p0.get('power', '?')}  |  P1 hp {p1.get('hp', '?'):>11}"
               f" act {p1.get('action', '?'):>5}")
        key = row[10:]
        print(row if key != prev else row[:10] + "  (same)")
        prev = key


def ppm_to_png(src, dst, half=True):
    d = open(src, "rb").read()
    head = d.split(b"\n", 3)
    w, h = map(int, head[1].split())
    px = head[3]
    rows = []
    step = 2 if half else 1
    for y in range(0, h, step):
        row = px[y * w * 3:(y + 1) * w * 3]
        if half:
            row = b"".join(row[x * 3:x * 3 + 3] for x in range(0, w, 2))
        rows.append(b"\0" + row)
    ow, oh = (w + step - 1) // step, (h + step - 1) // step

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    with open(dst, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", ow, oh, 8, 2, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(b"".join(rows), 6)) + chunk(b"IEND", b""))


def shot(dst, half=True):
    ppm = os.path.join(BOX, "shot.ppm")
    ans = send([f"shot {ppm}"])
    if not ans.startswith("shot"):
        return ans
    ppm_to_png(ppm, dst, half)
    return "shot " + dst


def contact_sheet(ppms, dst, cols=4, scale=4):
    """One PNG with the screenshots side by side, each shrunk `scale` times."""
    tiles = []
    for p in ppms:
        d = open(p, "rb").read()
        head = d.split(b"\n", 3)
        w, h = map(int, head[1].split())
        px = head[3]
        tw, th = w // scale, h // scale
        rows = [b"".join(px[((y * scale) * w + x * scale) * 3:((y * scale) * w + x * scale) * 3 + 3] for x in range(tw))
                for y in range(th)]
        tiles.append((tw, th, rows))
    if not tiles:
        return None
    tw, th = tiles[0][0], tiles[0][1]
    n_rows = (len(tiles) + cols - 1) // cols
    gap = 2
    W, H = cols * tw + (cols - 1) * gap, n_rows * th + (n_rows - 1) * gap
    lines = [bytearray(b"\x30" * (W * 3)) for _ in range(H)]
    for i, (_, _, rows) in enumerate(tiles):
        ox, oy = (i % cols) * (tw + gap), (i // cols) * (th + gap)
        for y, row in enumerate(rows):
            lines[oy + y][ox * 3:ox * 3 + len(row)] = row

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    raw = b"".join(b"\0" + bytes(l) for l in lines)
    with open(dst, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    return dst


def experiment(inputs, pack=None, p0=0, p1=11, mode=6, shots=0, shots_every=10, shots_after=0, settle=400,
               out=None, fresh=True, fast=True):
    """One test in one call: applies `pack` (None: keep the mods as they are, "--none": no mods), starts the battle
    p0 against p1 (fresh=False: a rematch of the current one), plays the inputs (macros allowed), takes `shots`
    screenshots every `shots_every` frames from `shots_after` vertical blanks after the inputs start, waits `settle`
    blanks after the inputs and returns {damage, hits, actions, anims, log, sheet}."""
    ensure()
    if pack is not None:
        apply(pack)
    cmds = []
    if fresh:
        cmds.append(f"fight {p0} 0 {p1} 0 0 {-1 if mode == 6 else -2} {mode}")
    else:
        cmds.append("restart")
    cmds += ["log"] + (["speed fast"] if fast and not shots else []) + expand(inputs)
    prefix = None
    if shots:
        out = out or os.path.join(BOX, "exp")
        prefix = out + "_shot"
        cmds += [f"wait {shots_after}", f"shots {shots} {shots_every} {prefix}"]
    cmds += ["sync", f"wait {settle}", "log", "speed normal", "state"]
    ans = send(cmds, timeout=180)
    if ans.startswith("error"):
        return {"error": ans}
    lines = ans.splitlines()
    logs = [l for l in lines if l.startswith(("hit", "action", "anim"))]
    res = {
        "damage": [int(x.split("=")[1]) for x in [l for l in lines if l.startswith("log ")][-1].split() if x.startswith("damage")],
        "hits": [(l.split()[2], int(l.split()[3].split("=")[1])) for l in lines if l.startswith("hit")],
        "actions": [(l.split()[2], l.split()[3]) for l in lines if l.startswith("action")],
        "anims": [(l.split()[2], l.split()[3]) for l in lines if l.startswith("anim")],
        "state": parse_state([l for l in lines if l.startswith("state")][-1]),
        "log": logs,
    }
    if shots:
        ppms = [f"{prefix}_{i:03d}.ppm" for i in range(shots) if os.path.exists(f"{prefix}_{i:03d}.ppm")]
        res["sheet"] = contact_sheet(ppms, out + "_sheet.png")
    return res


def summary(res):
    if "error" in res:
        return res["error"]
    p0a = " ".join(a for p, a in res["actions"] if p == "p0")
    p0n = " ".join(a for p, a in res["anims"] if p == "p0")
    hits1 = [d for p, d in res["hits"] if p == "p1"]
    hits0 = [d for p, d in res["hits"] if p == "p0"]
    return (f"damage to P1: {sum(hits1)} in {len(hits1)} hits {hits1}\n"
            f"damage to P0: {sum(hits0)} in {len(hits0)} hits\n"
            f"P0 actions: {p0a}\nP0 anims:   {p0n}\n" + (f"sheet: {res['sheet']}\n" if res.get("sheet") else ""))


def apply(pack_path):
    g = game.Game(DATA)
    if running():
        send(["release"])  # the game closes the files it holds open: Windows would not let them be replaced
    for attempt in range(30):  # (a program that just crashed lets go of its files a moment later)
        try:
            if pack_path == "--none":
                return "removed %d files" % g.remove()
            return "applied, %d files" % g.apply(modpack.load(pack_path))
        except PermissionError:
            if attempt == 29:
                raise
            time.sleep(0.2)


def stop(quiet=True):
    """Closes the test game (asked to quit, killed if it does not)."""
    if running():
        try:
            send(["quit"], timeout=5)
        except Exception:
            pass
        for _ in range(50):
            if not running():
                break
            time.sleep(0.1)
        kill()
    if not quiet:
        print("stopped")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "start":
        start(menus="--menus" in a)
    elif a[0] == "send":
        print(send(expand(a[1:])), end="")
    elif a[0] == "shot":
        print(shot(a[1], "--full" not in a))
    elif a[0] == "apply":
        print(apply(a[1]))
    elif a[0] == "stop":
        stop(quiet=False)
    elif a[0] == "try":  # try PACK|- P0 P1 "inputs" [shots]
        res = experiment(a[4].split(","), None if a[1] == "-" else a[1], int(a[2]), int(a[3]),
                         shots=int(a[5]) if len(a) > 5 else 0)
        print(summary(res), end="")
    elif a[0] == "kill":
        kill()
        print("killed")
    elif a[0] == "timeline":  # timeline SAMPLES EVERY "cmd" "cmd" ...
        other, states = timeline(a[3:], int(a[1]), int(a[2]))
        for line in other:
            print(line)
        show(states)
    else:
        print(__doc__)
