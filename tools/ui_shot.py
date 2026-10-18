"""Screenshots of the tool's own window, to check the interface without a person at the screen.
    py -I tools/ui_shot.py OUT_DIR STEP ...
Steps: select:N  tab:NAME  set:KEY=VALUE  base:N  menu:N=TEXT  graft:SLOT=FROM/FROMSLOT  skill:SLOT=FROM/FROMSLOT  search:TEXT
       scroll:FRACTION  picker  share  help  zoom:SCALE  focus:TAB  shot:NAME  wait:MS  size:WxH
The window is fully transparent (PrintWindow still gets its picture), so nothing shows on the desktop."""
import ctypes
import os
import sys
import time
import zlib
import struct
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def capture(hwnd, path):
    """Picture of a window (even hidden behind others or off the screen) as a PNG file."""
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]
    bih = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    bgra = buf.raw
    rgb = bytearray(w * h * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(rgb[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    return path


def main(out, steps):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    import studio
    import studio_ui as ui
    from bt3mod import game, modpack
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    studio.Studio.HIDDEN = True
    app = studio.Studio(game.find_gamedata())
    # On the screen (a window off the screen is not drawn again) but fully transparent: nobody sees it, and
    # PrintWindow still gets what it draws.
    app.attributes("-alpha", 0.0)
    app.update()
    print(f"window ready in {time.time() - t0:.2f} s")
    for step in steps:
        cmd, _, arg = step.partition(":")
        if cmd == "size":
            w, h = arg.split("x")
            app.geometry(f"{w}x{h}")
        elif cmd == "select":
            app.select(int(arg))
        elif cmd == "tab":
            app.show_tab((arg))
        elif cmd == "search":
            app.search.set(arg)
        elif cmd == "scroll":
            app.update()
            app.pages[app._page()].canvas.yview_moveto(float(arg))
        elif cmd == "set":
            key, _, v = arg.partition("=")
            app.show_tab(({"roster": "Stats", "param": "Stats", "melee": "Stats", "kiblast":
                                                "Rafales de ki", "move": "Déplacements"}.get(key.split(".")[0],
                                                                                              "Attaques")))
            app.update()
            app.rows[key].var.set(v)
        elif cmd == "base":
            c, _, b = arg.partition("=")
            app.select(int(c))
            app._set_base(int(b))
        elif cmd == "menu":
            c, _, text = arg.partition("=")
            modpack.chara(app.pack, int(c))["menuName"] = text
            app.select(int(c))
        elif cmd == "graft":
            slot, _, src = arg.partition("=")
            frm, _, fs = src.partition("/")
            app._set_graft("super", int(slot), int(frm), int(fs))
        elif cmd == "skill":
            slot, _, src = arg.partition("=")
            frm, _, fs = src.partition("/")
            app._set_graft("skill", int(slot), int(frm), int(fs))
        elif cmd == "wait":
            end = time.time() + int(arg) / 1000
            while time.time() < end:
                app.update()
                time.sleep(0.02)
        elif cmd == "picker":
            names = [app.target_text(k) for k in range(game.CHARA_COUNT)]
            ui.Picker.HIDDEN = True  # (transparent, like the main window)
            p = ui.Picker(app, "Mettre un personnage à la place de Pilaf Machine", names, dict(app.icons),
                          allow_none="Garder l'original", current=33)
            p.grab_release()
            for _ in range(10):
                app.update()
                time.sleep(0.02)
            capture(int(p.wm_frame(), 16), os.path.join(out, "picker.png"))
            p.destroy()
        elif cmd == "zoom":
            app.set_zoom(float(arg), save=False)  # (the person's own setting is left as it is)
        elif cmd == "focus":  # the keyboard's focus on a tab button (its orange border)
            app.tab_buttons[arg].focus_set()
            app.tab_buttons[arg].state(["focus"])  # (an invisible window never has the focus itself)
        elif cmd == "help":
            ui.InfoDialog.HIDDEN = True
            app.show_help()
            d = [w for w in app.winfo_children() if isinstance(w, ui.InfoDialog)][-1]
            for _ in range(10):
                app.update()
                time.sleep(0.02)
            capture(int(d.wm_frame(), 16), os.path.join(out, "help.png"))
            d.destroy()
        elif cmd == "share":
            ui.ShareDialog.HIDDEN = True
            app.share_pack()
            d = app.share_dialog
            d.grab_release()
            for _ in range(10):
                app.update()
                time.sleep(0.02)
            capture(int(d.wm_frame(), 16), os.path.join(out, "share.png"))
            d.destroy()
        elif cmd == "shot":
            for _ in range(10):
                app.update()
                time.sleep(0.02)
            print(capture(int(app.wm_frame(), 16), os.path.join(out, arg + ".png")))
    app.destroy()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
