"""Opens the character select of the test game with a pack applied and takes screenshots of chosen grid cells.
    py -I tools/menu_check.py PACK.json [CELL ...]      CELL = moves from the first cell, e.g. "right*3", "down*2+right"
Writes testkit/mailbox/menu_check.png (one picture per cell, the first one without any move)."""
import os
import time
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit  # noqa: E402

TO_SELECT = [("-", 2600), ("start", 150), ("cross", 200), ("down", 90), ("down", 90), ("down", 90), ("cross", 200),
             ("cross", 150), ("cross", 300)]


def press(btn, wait):
    cmds = [] if btn == "-" else [f"hold 4 {btn}", "sync"]
    # The logos at start-up (a wait without a press) at full speed. Not the waits after a press: a screen that loads
    # takes real time, and at full speed a wait counted in frames would end before it is there.
    kit.send(cmds + (["speed fast", f"wait {wait}", "speed normal"] if btn == "-" else [f"wait {wait}"]))


def wait_menu(mode, timeout=30):
    """Waits until the game shows the menu screen `mode` (gProgress->mode), then lets it settle."""
    t = time.time()
    while time.time() - t < timeout:
        if kit.parse_state(kit.send(["state"]).strip()).get("menu") == str(mode):
            kit.send(["wait 60"])
            return True
        kit.send(["wait 10"])
    return False


def moves(spec):
    out = []
    for part in [p for p in spec.split("+") if p]:
        btn, _, n = part.partition("*")
        out += [btn] * int(n or 1)
    return out


LAST_MENU = None  # the menu mode reached (39 = character select)


def main(pack, cells, quiet=False):
    global LAST_MENU
    kit.kill()
    r = kit.apply(pack)
    if not quiet:
        print(r)
    kit.start(quiet=True, menus=True, sound=True)
    kit.send(["unlock", "wait 5"])  # every character on the grid (the test save has most locked)
    for btn, wait in TO_SELECT:
        press(btn, wait)
    wait_menu(39)
    LAST_MENU = kit.parse_state(kit.send(["state"]).strip()).get("menu")
    if LAST_MENU != "39":
        print("not on the character select: menu", LAST_MENU)
    shots = []
    for i, cell in enumerate([""] + cells):
        for b in moves(cell):
            press(b, 25)
        press("-", 60)
        p = os.path.join(kit.BOX, f"menu_check_{i}.ppm")
        kit.send([f"shot {p}"])
        shots.append(p)
        for b in reversed(moves(cell)):  # back to the first cell
            press({"right": "left", "left": "right", "up": "down", "down": "up"}[b], 25)
    sheet = kit.contact_sheet(shots, os.path.join(kit.BOX, "menu_check.png"), cols=min(4, len(shots)), scale=2)
    if not quiet:
        print(sheet)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
    kit.stop()  # (the test game is closed at the end)
