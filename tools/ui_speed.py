"""How long the window takes to show another character or another tab (the window is invisible).
    py -I tools/ui_speed.py"""
import ctypes
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    import studio
    from bt3mod import game
    studio.Studio.HIDDEN = True
    t0 = time.time()
    app = studio.Studio(game.find_gamedata())
    app.update()
    print(f"window ready: {time.time() - t0:.2f} s")
    end = time.time() + 3  # (pictures loaded, pages made in the background)
    while time.time() < end:
        app.update()
        time.sleep(0.01)

    def timed(what, action):
        t = time.time()
        action()
        app.update()  # (drawn)
        return (time.time() - t) * 1000

    for label, ids in (("next character (pictures ready)", [1, 2, 3, 4]),
                       ("far character (picture made now)", [120, 60, 140]),
                       ("character seen before", [1, 120])):
        ms = [timed(label, lambda c=c: app.select(c)) for c in ids]
        print(f"{label:34} " + "  ".join(f"{m:5.0f} ms" for m in ms))
        for _ in range(30):  # (the prefetch thread)
            app.update()
            time.sleep(0.01)
    ms = [timed("tab", lambda i=i: app.show_tab(studio.PAGES[i])) for i in (1, 2, 3, 4, 0, 1)]
    print(f"{'tab change':34} " + "  ".join(f"{m:5.0f} ms" for m in ms))
    app.destroy()


if __name__ == "__main__":
    main()
