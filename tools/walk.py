"""Walks the game's own menus in the test game (kit.start(menus=True)) one input at a time, with a screenshot after
each, so a script of menu inputs can be checked screen by screen.
    py -I tools/walk.py STEP [STEP ...]     STEP = button[:wait]   (wait in vertical blanks after the press, 90)
Prints the menu mode after each step and writes a contact sheet testkit/mailbox/walk.png."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit  # noqa: E402


def menu():
    st = kit.parse_state(kit.send(["state"]).strip())
    return st.get("menu")


def walk(steps, sheet=True):
    shots = []
    for i, step in enumerate(steps):
        btn, _, wait = step.partition(":")
        cmds = [] if btn == "-" else [f"hold 4 {btn}", "sync"]
        kit.send(cmds + [f"wait {int(wait or 90)}"])
        p = os.path.join(kit.BOX, f"walk_{i:02d}.ppm")
        kit.send([f"shot {p}"])
        shots.append(p)
        print(f"{i:2d} {step:12} menu {menu()}", flush=True)
    if sheet and shots:
        print(kit.contact_sheet(shots, os.path.join(kit.BOX, "walk.png"), cols=4, scale=3))


if __name__ == "__main__":
    walk(sys.argv[1:])
