"""Uses the window like a person would (transparent, nothing on the screen) on the TEST game's data, checks the pack
it makes, then applies that pack to the test game and checks it in a battle.
    py -I tools/ui_check.py          (about 30 s; the player's own game is never touched)"""
import ctypes
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import kit  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name:46} {detail}", flush=True)


def pump(app, n=5):
    for _ in range(n):
        app.update()
        time.sleep(0.01)


def main():
    sys.stdout.reconfigure(errors="replace")  # (names with arrows on a console that has no such characters)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    from tkinter import messagebox
    import studio
    from bt3mod import modpack

    def refuse(*a, **k):
        raise AssertionError("unexpected dialog: %s" % (a,))
    messagebox.showwarning = messagebox.showerror = messagebox.askyesno = refuse  # (a dialog would wait forever)

    t0 = time.time()
    studio.Studio.HIDDEN = True
    app = studio.Studio(kit.DATA)
    app.attributes("-alpha", 0.0)
    pump(app)
    check("window opens on the test game's data", app.game.root == kit.DATA, f"{time.time() - t0:.2f} s")

    # Pilaf Machine (152) <- Vegeta (31), its Fusion (153) <- Super Vegeta (33)
    app.select(153)
    app._set_base(33)
    app.select(152)
    app._set_base(31)
    # values: health on the Stats page, the Ultimate's damage on the Attaques page
    app.show_tab(("Stats"))
    pump(app)
    app.rows["roster.health"].var.set("60000")
    app.rows["roster.kiStart"].var.set("100000")
    app.rows["param.blastGain"].var.set("1000000")
    app.show_tab(("Attaques"))
    pump(app)
    warned = []
    messagebox.showwarning = lambda title, text: warned.append(text)
    app._set_graft("super", 2, 33, 2)  # Super Vegeta's Final Flash as the Ultimate: its effects do not fit a Vegeta
    messagebox.showwarning = refuse
    check("a graft too big for the game is refused at once", len(warned) == 1 and "ne rentre pas" in warned[0]
          and not app.pack["characters"]["152"].get("transplants"), warned[0][:90] if warned else "no warning")
    app._set_graft("super", 2, 33, 0)  # Super Vegeta's Big Bang Attack as the Ultimate
    app._set_graft("skill", 1, 0, 0)  # Goku (Early)'s Solar Flare as the Blast 1 n°2
    pump(app)
    app.rows["super.damage.2"].var.set("22220")
    # transformations: R3 + right -> Goku (End) Super Saiyan 3, cost 3; and it is offered in the grid cell
    app.show_tab(("Personnage"))
    pump(app)
    app._set_transform(2, {"to": 6, "cost": 3})
    app._set_form(3, 6)
    ch = app.pack["characters"]["152"]
    ch["menuName"] = "Prince Vegeta"  # (the entry's own handler is checked below with a real keystroke path)
    pump(app)

    # the mouse wheel over the list of the grafted attack: the page glides down, the attack chosen stays
    app.show_tab("Attaques")
    pump(app, 10)
    combo = next(c for c in app.atk_cards if c["kind"] == "super" and c["slot"] == 2)["combo"]
    chosen, page = combo.get(), app.pages["Attaques"]
    page.top()
    pump(app, 5)
    for _ in range(3):
        combo.event_generate("<MouseWheel>", delta=-120)
    pump(app, 40)
    moved = page.canvas.canvasy(0)
    check("the wheel scrolls the page, not a list's value", moved > 100 and combo.get() == chosen,
          f"page moved {moved:.0f} px, list {combo.get()!r}")
    # the keyboard: Ctrl+↓ the next character of the list, Ctrl+3 the Stats tab, Ctrl+↑ back
    tree = app.list.tree
    tree.focus_force()  # (Tk gives a key to the widget that has the keyboard: without it, the keys are lost)
    pump(app)
    tree.event_generate("<Control-Down>")
    tree.event_generate("<Control-Key-3>")
    pump(app)
    went = (app.chara, app.current)
    tree.event_generate("<Control-Up>")
    pump(app)
    if app.focus_get() is None:  # (another program has the keyboard: Windows does not let a test take it)
        print("SKIP  keyboard shortcuts (Ctrl+↓, Ctrl+3, Ctrl+↑)          another program has the keyboard",
              flush=True)
    else:
        check("keyboard shortcuts (Ctrl+↓, Ctrl+3, Ctrl+↑)", went == (153, "Stats") and app.chara == 152,
              f"{went} then {app.chara}")
    app.show_tab("Personnage")
    pump(app)

    # an added character (the extended edition): made from Vegeta, 7 bars of health, Super Vegeta's Big Bang as its
    # Ultimate; its name typed in the Personnage page
    modpack.add(app.pack, 31, "Vegeta (nouveau)")
    app.refresh_list()
    added = studio.ADDED + len(app.added()) - 1
    app.select(added)
    app.show_tab("Personnage")
    pump(app)
    app.menu_vars["menuName"].set("Vegeta X")
    app.show_tab("Stats")
    pump(app)
    app.rows["roster.health"].var.set("900000")  # (out of bounds: the maximum is kept, and said next to the box)
    pump(app)
    kept, said = app.added()[-1]["fields"].get("roster.health"), app.rows["roster.health"].info.cget("text")
    check("a value too high: the maximum kept, said next to it", kept == 150000 and "150000" in said,
          f"kept {kept}, says « {said} »")
    app.rows["roster.health"].var.set("70000")
    app.rows["roster.kiStart"].var.set("100000")  # (an Ultimate needs ki)
    app._set_graft("super", 2, 33, 0)
    pump(app)
    e = app.added()[-1]
    check("an added character made in the window", e.get("name") == "Vegeta X" and e.get("base") == 31
          and e["fields"].get("roster.health") == 70000 and e["fields"].get("roster.kiStart") == 100000
          and e.get("transplants") == [{"slot": 2, "from": 33,
                                                                                      "fromSlot": 0}]
          and "＋ Vegeta X" in app._row_text(added), str({k: e[k] for k in e if k != "texts"}))
    # the list's right-click actions on an added character: duplicate, then delete the copy
    app.duplicate_added()
    pump(app)
    copied = len(app.added()) == 2 and app.added()[1]["name"] == "Vegeta X (copie)" and app.chara == added + 1
    messagebox.askyesno = lambda *a, **k: True  # (the "delete?" question answered yes)
    app.delete_added()
    messagebox.askyesno = refuse
    pump(app)
    check("an added character duplicated, then the copy deleted", copied and len(app.added()) == 1 and
          str(added + 1) not in app.list.tree.get_children(), f"copied {copied}, left {len(app.added())}")
    app.select(added)
    pump(app)

    # the edition switch: in the standard one the added character is out of the list (kept in the pack) and the
    # buttons of the extended one are off; back in the extended one, all is there again
    app.game._cache["edition"] = "officielle"  # (as if the official game were installed)
    app.sync_edition()
    pump(app)
    hidden = (str(added) not in app.list.tree.get_children() and str(app.add_btn.cget("state")) == "disabled"
              and len(app.added()) == 1 and app.chara != added)
    app.game._cache["edition"] = "etendu"
    app.sync_edition()
    pump(app)
    back = str(added) in app.list.tree.get_children() and str(app.add_btn.cget("state")) == "normal"
    check("the tool follows the game: official hides the added one", hidden and back, f"hidden {hidden}, back {back}")
    app.select(152)
    app.show_tab("Personnage")
    pump(app)

    expect = {"base": 31, "transplants": [{"slot": 2, "from": 33, "fromSlot": 0},
                                          {"kind": "skill", "slot": 1, "from": 0, "fromSlot": 0}],
              "fields": {"roster.health": 60000, "roster.kiStart": 100000, "param.blastGain": 1000000,
                         "super.damage.2": 22220},
              "transforms": [{"to": 32, "cost": 1}, {"to": 153, "cost": 2}, {"to": 6, "cost": 3}, None],
              "forms": [152, 32, 153, 6], "menuName": "Prince Vegeta"}
    got = {k: ch.get(k) for k in expect}
    check("the pack holds what was done in the window", got == expect,
          "" if got == expect else f"\n   got    {got}\n   expect {expect}")
    check("list and header follow", "→" in app._row_text(152) and "Vegeta" in app.title_var.get()
          and app.state_lbl.cget("text").startswith("●"), app._row_text(152).strip())

    path = os.path.join(tempfile.mkdtemp(prefix="bt3ui_"), "ui.bt3mod.json")
    app._sync_meta()
    modpack.save(app.pack, path)
    back = modpack.load(path)
    check("saved pack reads back the same", back["characters"]["152"] == modpack.clean(app.pack)["characters"]["152"])

    # sharing by code: the code gives the same pack back; a friend's code replaces the open pack; a cut code is refused
    code = modpack.to_code(app.pack)
    same = modpack.from_code(code)["characters"] == modpack.clean(app.pack)["characters"]
    app.saved = app._snapshot()  # (no "save first?" dialog)
    friend = modpack.new("Pack d'un ami", "Krillin")
    modpack.chara(friend, 25)["fields"]["roster.health"] = 20000
    err = app._load_code(modpack.to_code(friend)[:30] + "\n" + modpack.to_code(friend)[30:])
    loaded = err is None and app.pack["characters"] == modpack.clean(friend)["characters"] \
        and app.pack_name.get() == "Pack d'un ami"
    bad = app._load_code(modpack.to_code(friend)[:-12])
    check("share code: same pack back, a friend's loads, a cut one refused", same and loaded and bool(bad),
          f"{len(code)} characters, mark {modpack.fingerprint(back)}")
    app.destroy()

    # in the test game: the copy's health and Ultimate damage, then R3 + right to Goku (End) Super Saiyan 3
    t = time.time()
    kit.stop()  # (the game reads the folder of added characters when it starts)
    kit.apply(path)
    kit.ensure()
    r = kit.experiment(["ultimate"], p0=152, p1=11, settle=600)
    hits = [d for s, d in r.get("hits", []) if s == "p1"]
    st = r.get("state", {}).get("p0", {})
    check("in the game: health 60000 and the grafted Big Bang", st.get("hp", "").endswith("/60000") and
          sum(hits) > 20000, f"hp {st.get('hp')}, {len(hits)} hits = {sum(hits)}  ({time.time() - t:.1f} s)")
    ans = kit.send(["unlock", "fight 152 0 11 0", "speed fast", "hold 60 -", "hold 4 r3+right", "hold 4 right",
                    "sync", "wait 200", "speed normal", "state"])
    seen = [kit.parse_state(l)["p0"].get("chara") for l in ans.splitlines() if l.startswith("state")]
    check("in the game: R3 + right turns into Goku (End) SSJ3", seen == ["6"], f"chara {seen}")
    r = kit.experiment(["ultimate"], p0=198, p1=11, settle=600)  # (198: the first added character)
    hits = [d for s, d in r.get("hits", []) if s == "p1"]
    st = r.get("state", {}).get("p0", {})
    check("in the game: the added character, 70000 and the Big Bang", st.get("chara") == "198" and
          st.get("hp", "").endswith("/70000") and len(hits) == 4, f"chara {st.get('chara')}, hp {st.get('hp')}, "
                                                                   f"{len(hits)} hits = {sum(hits)}")
    kit.apply("--none")
    kit.stop()  # (the test game is closed at the end)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
