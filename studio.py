"""BT3 Mod Studio: a window to change the characters of Dragon Ball Z Budokai Tenkaichi 3 (Tenkaichi3Decomp)."""
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bt3mod import appcache, fields, forms, game, menunames, modpack, roster, transplant  # noqa: E402
import studio_ui as ui  # noqa: E402
from studio_ui import px  # noqa: E402

TITLE = "BT3 Mod Studio"
NAME_LANGS = [("en", "Anglais (jeu US)"), ("fr", "Français")]
TRANSFORM_KEYS = ["R3 + ←", "R3 + ↑", "R3 + →", "R3 + ↓   retour"]
# the special moves in the order of the move list: (title, fields prefix, slot, index in the list)
SPECIALS = [("Blast 1 n°1", "skill", 0, 0), ("Blast 1 n°2", "skill", 1, 1), ("Blast 2 n°1", "super", 0, 2),
            ("Blast 2 n°2", "super", 1, 3), ("Ultime", "super", 2, 4)]
KIBLAST_COLS = [("damage", "Dégâts"), ("guardDamage", "Si gardé"), ("ki", "Coût en ki"), ("speed", "Vitesse"),
                ("turn", "Guidage"), ("time", "Durée"), ("hits", "Coups")]
PAGES = ["Personnage", "Attaques", "Stats", "Rafales de ki", "Déplacements"]


def fmt(f, v):
    if f.is_float:
        return ("%.3f" % v).rstrip("0").rstrip(".")
    return str(int(v))


def plural(v, word):
    return f"{v:g} {word}" + ("s" if abs(v) >= 2 else "")


def meaning(f, v):
    """What a value means in the game's own units, e.g. "1,35 barre de vie"."""
    h = f.hint
    per = "/s" if "par seconde" in h else ""
    if h.startswith("10000 = 1 barre"):
        return plural(round(v / fields.HP_BAR, 2), "barre").replace(".", ",") + " de vie" + per
    if "20000 = 1 barre" in h:
        return plural(round(v / fields.KI_BAR, 2), "barre").replace(".", ",") + " de ki" + per
    if "100000 = 1 stock" in h:
        return plural(round(v / 100000, 2), "stock").replace(".", ",") + per
    return ""


class FieldRow:
    """A value of the character: a box, what the value means, its original value and a button to put it back."""

    def __init__(self, app, parent, f, label=None, compact=False):
        self.app, self.f, self.compact = app, f, compact
        self.var = tk.StringVar()
        self.label = None if compact else ttk.Label(parent, text=label or f.label, style="Card.TLabel")
        self.ent = ui.entry(parent, self.var, width=7 if compact else 11, justify="right")
        # (fixed sizes: a value that changes never moves the page's layout, which is what makes Tk slow)
        self.info = None if compact else ttk.Label(parent, text="", style="Card.Muted.TLabel", width=32)
        self.reset = None if compact else ttk.Button(parent, text="", style="Link.TButton", width=11,
                                                     command=self.revert)
        self.page = app.building
        if self.reset:
            ui.Tooltip(self.reset, "Remettre la valeur d'origine")
        self.ent.bind("<Button-3>", lambda e: self.revert())
        ui.Tooltip(self.ent, self.tip)
        self.var.trace_add("write", lambda *a: app.on_field(self))
        app.rows[f.key] = self

    def grid(self, row, col=0):
        if self.compact:
            self.ent.grid(row=row, column=col, padx=px(3), pady=px(3))
            return
        c = col * 4
        self.label.grid(row=row, column=c, sticky="w", padx=(0, px(10)), pady=px(3))
        self.ent.grid(row=row, column=c + 1, sticky="w", pady=px(3))
        self.info.grid(row=row, column=c + 2, sticky="w", padx=(px(8), 0))
        self.reset.grid(row=row, column=c + 3, sticky="w", padx=(px(2), px(22)))

    def tip(self):
        o = self.app.orig.get(self.f.key)
        text = f"{self.f.slot} · {self.f.label}\n{self.f.hint}" if self.compact else self.f.hint
        if o is not None:
            text += f"\nOrigine : {fmt(self.f, o)}" + (f" ({meaning(self.f, o)})" if meaning(self.f, o) else "")
        if self.compact:
            text += "\nClic droit : remettre la valeur d'origine"
        return text

    def show(self, value):
        self.var.set(fmt(self.f, value))
        self.paint(value)

    def changed(self):
        return self.f.key in self.app.chara_fields()

    def paint(self, value=None, bad=False):
        changed = self.changed()
        if bad:
            self.ent.configure(bg=ui.BAD_BG, fg=ui.TEXT)
        else:
            self.ent.configure(bg=ui.MOD_BG if changed else ui.FIELD, fg=ui.MOD_TEXT if changed else ui.TEXT)
        if self.compact:
            return
        o = self.app.orig.get(self.f.key)
        text = meaning(self.f, value) if value is not None and not bad else ""
        if changed and o is not None:
            text += ("   " if text else "") + f"origine {fmt(self.f, o)}"
        self.info.configure(text=text)
        self.reset.configure(text="↺ remettre" if changed else "")

    def revert(self):
        o = self.app.orig.get(self.f.key)
        if o is not None:
            self.var.set(fmt(self.f, o))


class CharButton:
    """A button showing a character (its chip and name) or a text; clicking it opens a picker."""

    def __init__(self, app, parent, none_text, command, width=36):
        self.app, self.none_text, self.command, self.active = app, none_text, command, True
        self.b = ttk.Button(parent, style="Char.TButton", width=width, command=self._click, compound="left")
        self.set(None)

    def _click(self):
        if self.active and self.command:
            self.command()

    def set(self, c, none_text=None, active=True, ghost=False):
        """Shows character c (None: the text). active=False: a click does nothing (never "disabled": Tk would
        grey the chip with a hatch); ghost: an empty place, drawn like the card under it."""
        if none_text is not None:
            self.none_text = none_text
        self.active = active
        img = self.app.small_icon(c) if c is not None else None
        self.b.configure(text="  " + (self.app.target_text(c) if c is not None else self.none_text),
                         image=img if img is not None else self.app.blank,
                         style="Ghost.TButton" if ghost else "Char.TButton",
                         cursor="hand2" if active and self.command else "")


class Studio(tk.Tk):
    HIDDEN = False  # the tests' screenshots keep the window invisible (tools/ui_shot.py, tools/ui_check.py)

    def __init__(self, gamedata):
        super().__init__()
        self.attributes("-alpha", 0.0)  # (shown once ready, with its dark title bar: _show)
        ui.setup(self)
        self.title(TITLE)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(px(1360), sw - px(40)), min(px(880), sh - px(90))
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        self.minsize(px(1060), px(620))
        self.game = game.Game(gamedata)
        self.pack = modpack.new()
        self.pack_path = None
        self.chara = None
        self.orig = {}
        self.rows = {}           # field key -> FieldRow of the pages built
        self.loading = False
        # the grid chips at their own size (64 pixels: sharp) on screens with a zoom, a little smaller without
        self.icon_size = 64 if ui.S >= 1.15 else 48
        self.small_size = px(32)  # (the chips on the buttons)
        self.blank = tk.PhotoImage(width=self.small_size, height=self.small_size)
        self.icons, self.small_icons = {}, {}  # character id -> chip PhotoImage, list size / button size
        self.faces = {}          # (character id, width) -> PhotoImage of its large picture
        self.face_png = {}       # the same as PNG, made ahead by a thread (_prefetch)
        self.prefetching = False
        self.built = set()       # pages made (once: then only their contents change)
        self.stale = set()       # pages made that do not show the selected character yet (filled when shown)
        self.building = None     # the page being made (FieldRow.page)
        self.applied = None      # the pack as it was last applied to the game (JSON)
        self.names = [roster.name(c) for c in range(game.CHARA_COUNT)]
        cached = appcache.load(self.game)
        self.moves = cached["moves"] if cached else None
        if cached:
            self.game._cache["grid"] = cached["grid"]
        try:
            self.iconphoto(True, tk.PhotoImage(data=ui.ball_png(32)), tk.PhotoImage(data=ui.ball_png(16)))
        except tk.TclError:
            pass

        self._build_top()
        self.status = tk.StringVar(value=f"Données du jeu : {gamedata}")
        bar = ttk.Frame(self, style="Panel.TFrame", padding=(px(12), px(4)))
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status, style="Panel.Muted.TLabel").pack(side="left")
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self._build_side(body)
        self._build_portrait(body)
        self._build_editor(body)
        self.saved = self._snapshot()  # the pack as it was last saved or opened
        self.refresh_list()
        self.select(0)
        self.bind_all("<Control-s>", lambda e: self.save_pack())
        self.bind_all("<Control-o>", lambda e: self.open_pack())
        self.bind_all("<F5>", lambda e: self.apply())
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.pack_name.trace_add("write", lambda *a: self._dirty())
        self.after(10, self._show)
        self.after(120, self._load_assets)  # (after the first drawing of the window)
        self.after(700, self._build_all)

    def _show(self):
        """The window appears: dark title bar first (Windows 10 takes it at the next change of the window, here
        its opacity), then visible."""
        ui.dark_title(self, show=not self.HIDDEN)

    def _build_all(self):
        """Makes the pages not shown yet, one at a time while nothing else happens: a tab then opens at once."""
        for name in PAGES:
            if name not in self.built:
                self._build_page(name)
                self.after(60, self._build_all)
                return

    # ---- the window --------------------------------------------------------------------------------------------
    def _build_top(self):
        top = ttk.Frame(self, style="Panel.TFrame", padding=(px(14), px(10), px(14), px(10)))
        top.pack(fill="x")
        tk.Frame(self, bg=ui.ACCENT, height=px(2)).pack(fill="x")
        self.logo = tk.PhotoImage(data=ui.ball_png(px(30)))
        ttk.Label(top, image=self.logo, style="Panel.TLabel").pack(side="left")
        ttk.Label(top, text=TITLE, style="AppTitle.Panel.TLabel").pack(side="left", padx=(px(8), px(26)))
        ttk.Label(top, text="Pack", style="Panel.Muted.TLabel").pack(side="left")
        self.pack_name = tk.StringVar(value=self.pack["name"])
        ttk.Entry(top, textvariable=self.pack_name, width=22).pack(side="left", padx=(px(6), px(10)))
        ttk.Label(top, text="par", style="Panel.Muted.TLabel").pack(side="left")
        self.pack_author = tk.StringVar()
        ttk.Entry(top, textvariable=self.pack_author, width=14).pack(side="left", padx=(px(6), px(14)))
        for text, cmd in (("Nouveau", self.new_pack), ("Ouvrir…", self.open_pack), ("Enregistrer…", self.save_pack),
                          ("Partager…", self.share_pack)):
            ttk.Button(top, text=text, command=cmd).pack(side="left", padx=(0, px(6)))
        ttk.Button(top, text="▶  Appliquer au jeu", style="Accent.TButton", command=self.apply).pack(side="right")
        ttk.Button(top, text="Retirer les mods du jeu", command=self.remove_mods).pack(side="right", padx=px(8))
        self.state_lbl = ttk.Label(top, text="", style="Panel.Muted.TLabel")
        self.state_lbl.pack(side="right", padx=px(10))
        ui.Tooltip(self.state_lbl, lambda: "Le jeu utilise ce pack tel qu'il est." if "✓" in
                   self.state_lbl.cget("text") else "Des changements de ce pack ne sont pas encore dans le jeu : "
                                                    "clique sur « Appliquer au jeu ».")

    def _build_side(self, parent):
        side = ttk.Frame(parent, style="Panel.TFrame", padding=(px(12), px(12), px(6), px(8)), width=px(330))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        ttk.Label(side, text="Personnages", style="Panel.Title.TLabel").pack(anchor="w")
        ttk.Label(side, text="Recherche par nom, attaque ou numéro", style="Panel.Muted.TLabel").pack(anchor="w")
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *a: self.refresh_list())
        ttk.Entry(side, textvariable=self.search, style="Search.TEntry").pack(fill="x", pady=(px(6), px(8)))
        seg = ttk.Frame(side, style="Panel.TFrame")
        seg.pack(fill="x", pady=(0, px(8)))
        self.only_mod = False
        self.seg_all = ttk.Button(seg, text="Tous", style="SegOn.TButton", command=lambda: self._filter_mod(False))
        self.seg_all.pack(side="left")
        self.seg_mod = ttk.Button(seg, text="Modifiés", style="Seg.TButton", command=lambda: self._filter_mod(True))
        self.seg_mod.pack(side="left", padx=(px(4), 0))
        self.count_lbl = ttk.Label(seg, text="", style="Panel.Muted.TLabel")
        self.count_lbl.pack(side="right", padx=px(4))
        self.list = ui.CharList(side, self.names, self.icons, on_select=self._on_list)
        self.list.pack(fill="both", expand=True)
        ttk.Style(self).configure("Treeview", rowheight=self.icon_size + px(8))

    def _build_portrait(self, parent):
        # The game draws its pictures in a frame of their own width (most are cut on both sides and at the bottom):
        # the panel is that frame, the picture fills its width.
        self.card_w = px(280)
        self.portrait = tk.Canvas(parent, width=self.card_w, highlightthickness=0, bd=0, bg=ui.SKY_BOTTOM)
        self.portrait.pack(side="right", fill="y")
        self.portrait.bind("<Configure>", lambda e: self._draw_portrait())

    def _build_editor(self, parent):
        main = ttk.Frame(parent)
        main.pack(side="left", fill="both", expand=True)
        head = ttk.Frame(main, padding=(px(20), px(14), px(16), px(6)))
        head.pack(fill="x")
        head.columnconfigure(0, weight=1)
        self.title_var = tk.StringVar()
        ttk.Label(head, textvariable=self.title_var, style="Big.TLabel").grid(row=0, column=0, sticky="w")
        right = ttk.Frame(head)
        right.grid(row=0, column=1, sticky="ne")
        ttk.Label(right, text="Surnom", style="Muted.TLabel").pack(side="left")
        self.nick_var = tk.StringVar()
        self.nick_var.trace_add("write", lambda *a: self._on_nick())
        ttk.Entry(right, textvariable=self.nick_var, width=18).pack(side="left", padx=px(8))
        ttk.Button(right, text="Réinitialiser", command=self.reset_chara).pack(side="left")
        ui.Tooltip(right.winfo_children()[-1], "Effacer tous les changements de ce personnage dans le pack")
        badges = ttk.Frame(head)
        badges.grid(row=1, column=0, columnspan=2, sticky="w", pady=(px(2), px(4)))
        self.badge_num = ttk.Label(badges, style="BadgeBlue.TLabel")
        self.badge_rep = ttk.Label(badges, style="Badge.TLabel")
        self.badge_mod = ttk.Label(badges, text="Modifié dans ce pack", style="Badge.TLabel")
        self.facts = ttk.Label(head, text="", style="Muted.TLabel")
        self.facts.grid(row=2, column=0, columnspan=2, sticky="w")
        # Tabs: a bar of buttons over pages stacked in one place, all of them shown; a tab brings its page to the
        # front (a Notebook hides and shows hundreds of little windows at each change: slow on Windows).
        bar = ttk.Frame(main)
        bar.pack(fill="x", padx=(px(10), 0))
        stack = ttk.Frame(main)
        stack.pack(fill="both", expand=True, padx=(px(10), 0))
        tk.Frame(stack, bg=ui.BORDER, height=1).place(x=0, y=0, relwidth=1)
        self.pages, self.tab_buttons, self.current = {}, {}, PAGES[0]
        for name in PAGES:
            b = ttk.Button(bar, text=name, style="Tab.TButton", command=lambda n=name: self.show_tab(n))
            b.pack(side="left")
            self.tab_buttons[name] = b
            p = ui.ScrollPage(stack)
            p.place(x=0, y=1, relwidth=1, relheight=1, height=-1)
            self.pages[name] = p
        self.show_tab(PAGES[0])

    def show_tab(self, name):
        self.current = name
        for n, b in self.tab_buttons.items():
            b.configure(style="TabOn.TButton" if n == name else "Tab.TButton")
        self._build_page(name)
        self.pages[name].tkraise()

    # ---- start-up pictures and searches -----------------------------------------------------------------------
    def _load_assets(self):
        """The chips (two sizes: the list's, the buttons') and the cached moves: from the cache, else made in a
        thread the first time."""
        sizes = (self.icon_size, self.small_size)
        if all(appcache.chips_ready(self.game, s) for s in sizes) and self.moves is not None:
            self._take_chips()
            return
        self.status.set("Première ouverture : préparation des portraits et de la recherche (quelques secondes)…")
        result = {}

        def work():
            try:
                if self.moves is None:
                    result["data"] = appcache.make(self.game)
                for s in sizes:
                    if not appcache.chips_ready(self.game, s):
                        appcache.make_chips(self.game, s)
            except Exception as e:  # (the window works without them)
                result["error"] = str(e)

        def done():
            if t.is_alive():
                self.after(150, done)
                return
            if "data" in result:
                self.moves = result["data"]["moves"]
                self.game._cache["grid"] = result["data"]["grid"]
            if "error" in result:
                self.status.set(f"Portraits indisponibles : {result['error']}")
            else:
                self._take_chips()
                self.status.set("Prêt.")
            self.refresh_list()
            self._refresh_pages()

        t = threading.Thread(target=work, daemon=True)
        t.start()
        self.after(150, done)

    def _chips(self, size):
        """{character id: PhotoImage} cut out of the chips picture of that size."""
        path, _ = appcache.chips_path(self.game, size)
        try:
            sheet = tk.PhotoImage(file=path)
        except tk.TclError:
            return {}
        out = {}
        for c in range(game.CHARA_COUNT):
            x, y = (c % appcache.COLS) * size, (c // appcache.COLS) * size
            img = tk.PhotoImage(width=size, height=size)
            img.tk.call(img, "copy", sheet, "-from", x, y, x + size, y + size)
            out[c] = img
        return out

    def _take_chips(self):
        self.icons.update(self._chips(self.icon_size))
        self.small_icons.update(self._chips(self.small_size))
        self.list.icons = self.icons
        self.refresh_list()
        self._refresh_pages()

    def icon(self, c):
        """The chip a slot shows (the list's size): a replaced slot shows its new character's."""
        return self.icons.get(self.base_of(c))

    def small_icon(self, c):
        """The same, the buttons' size."""
        return self.small_icons.get(self.base_of(c))


    # ---- character list ----------------------------------------------------------------------------------------
    def base_of(self, c):
        ch = self.pack["characters"].get(str(c), {})
        return int(ch["base"]) if "base" in ch else c

    def is_changed(self, c):
        ch = self.pack["characters"].get(str(c), {})
        return bool(ch.get("fields") or any(ch.get("texts", {}).values()) or ch.get("transplants") or "base" in ch
                    or ch.get("menuName") or ch.get("menuForm") or ch.get("transforms") is not None
                    or ch.get("forms") or ch.get("nickname"))

    def _row_text(self, c):
        ch = self.pack["characters"].get(str(c), {})
        text = "  " + self.names[c]
        if "base" in ch:
            text += "  →  " + self.names[int(ch["base"])]
        if ch.get("menuName"):
            text += f"  « {ch['menuName']} »"
        elif ch.get("nickname"):
            text += f"  « {ch['nickname']} »"
        return text

    def _row_tags(self, c):
        if "base" in self.pack["characters"].get(str(c), {}):
            return ("rep",)
        return ("mod",) if self.is_changed(c) else ()

    def target_text(self, k):
        """A character in the pickers and buttons: a slot this pack replaces says by whom."""
        b = self.base_of(k)
        return self.names[k] + (f"  →  {self.names[b]}" if b != k else "")

    def refresh_list(self):
        q = self.search.get().strip().lower()

        def match(c):
            if self.only_mod and not self.is_changed(c):
                return False
            if not q:
                return True
            hay = self._row_text(c).lower() + " %03d %d" % (c, c)
            if self.moves:
                hay += " " + " ".join(self.moves[c]).lower()
            return q in hay
        ids = [c for c in range(game.CHARA_COUNT) if match(c)]
        self.list.icons = {c: self.icon(c) for c in ids}
        self.list.fill(ids, self._row_text, self._row_tags)
        if self.chara in ids:
            self.list.select(self.chara)
        n = sum(1 for c in range(game.CHARA_COUNT) if self.is_changed(c))
        self.seg_mod.configure(text=f"Modifiés ({n})")
        self.count_lbl.configure(text=f"{len(ids)} affichés")

    def _filter_mod(self, on):
        self.only_mod = on
        self.seg_all.configure(style="Seg.TButton" if on else "SegOn.TButton")
        self.seg_mod.configure(style="SegOn.TButton" if on else "Seg.TButton")
        self.refresh_list()

    def _refresh_row(self):
        c = self.chara
        if str(c) in self.list.tree.get_children():
            kw = {"image": self.icon(c)} if self.icon(c) is not None else {}
            self.list.tree.item(str(c), text=self._row_text(c), tags=self._row_tags(c), **kw)
        n = sum(1 for k in range(game.CHARA_COUNT) if self.is_changed(k))
        self.seg_mod.configure(text=f"Modifiés ({n})")
        self._header()
        self._dirty()

    def _on_list(self, c):
        if c != self.chara:
            self.select(c)

    # ---- the selected character --------------------------------------------------------------------------------
    def ch(self):
        return self.pack["characters"].get(str(self.chara), {})

    def chara_fields(self):
        return self.ch().get("fields", {})

    def value(self, key):
        return self.chara_fields().get(key, self.orig.get(key))

    def select(self, c):
        """Shows character c: the widgets stay, only what they show changes (no page is made again)."""
        self.chara = c
        self.orig = self.game.start_values(c, self.ch())  # (what the slot holds before its numbers change)
        self.loading = True
        self.nick_var.set(self.ch().get("nickname", ""))
        self.loading = False
        self.stale = set(self.built)
        self._header()
        self._draw_portrait()
        self._build_page(self._page())
        self.list.select(c)
        self._prefetch()

    def _reselect(self):
        """Shows the character again after a change that moves its starting values (copy, graft...)."""
        self.select(self.chara)
        self._refresh_row()

    def _header(self):
        c, ch = self.chara, self.ch()
        base = self.base_of(c)
        self.title_var.set(self.names[c] + (f"   →   {self.names[base]}" if base != c else ""))
        for b in (self.badge_num, self.badge_rep, self.badge_mod):
            b.pack_forget()
        self.badge_num.configure(text=f"n°{c:03d}")
        self.badge_num.pack(side="left", padx=(0, px(6)))
        if base != c:
            self.badge_rep.configure(text=f"Remplacé par {self.names[base]}")
            self.badge_rep.pack(side="left", padx=(0, px(6)))
        if self.is_changed(c):
            self.badge_mod.pack(side="left")
        hp, ki, st = (self.value(k) for k in ("roster.health", "roster.kiStart", "roster.stocks"))
        names = self.game.start_move_names(c, ch)
        facts = [plural(round(hp / fields.HP_BAR, 1), "barre").replace(".", ",") + " de vie",
                 "ki au départ : " + plural(round(ki / fields.KI_BAR, 1), "barre").replace(".", ","),
                 plural(st, "blast stock")]
        if len(names) == 6:
            facts.append("Ultime : " + names[4].strip())
        self.facts.configure(text="   ·   ".join(facts))

    # ---- the large picture -------------------------------------------------------------------------------------
    def _face(self, c):
        key = (c, self.card_w)
        img = self.faces.get(key)
        if img is None:
            try:
                data = self.face_png.pop(key, None) or appcache.face(self.game, c, self.card_w)
                img = tk.PhotoImage(data=data)
            except Exception:
                return None
            if len(self.faces) > 40:
                self.faces.pop(next(iter(self.faces)))
            self.faces[key] = img
        return img

    def _prefetch(self):
        """Prepares the pictures of the characters around the selected one (a thread): the next click is quick."""
        if self.prefetching or self.chara is None:
            return
        ids = self.list.visible
        i = ids.index(self.chara) if self.chara in ids else 0
        todo = [self.base_of(c) for c in ids[max(0, i - 3):i + 4]]
        todo = [c for c in todo if (c, self.card_w) not in self.faces and (c, self.card_w) not in self.face_png]
        if not todo:
            return
        self.prefetching = True
        width = self.card_w

        def work():
            for c in todo:
                try:
                    self.face_png[(c, width)] = appcache.face(self.game, c, width)
                except Exception:
                    pass
            # then every other picture, slowly (a pause between two leaves the window all its speed), so that they
            # are all in the cache folder: from then on a picture is only a small file to read
            for c in range(game.CHARA_COUNT):
                if not appcache.face_ready(self.game, c, width):
                    try:
                        appcache.face(self.game, c, width)
                    except Exception:
                        pass
                    time.sleep(0.3)
            self.prefetching = False
        threading.Thread(target=work, daemon=True).start()

    def _draw_portrait(self):
        cv = self.portrait
        w, h = max(cv.winfo_width(), self.card_w), max(cv.winfo_height(), px(300))
        cv.delete("all")
        ui.gradient(cv, w, h, ui.SKY_TOP, ui.SKY_BOTTOM)
        if self.chara is None:
            return
        base = self.base_of(self.chara)
        img = self._face(base)
        plate = px(78)
        ih = img.height() if img is not None else px(400)
        top = max(0, h - plate - ih)  # (standing on the name plate; on a short window its cut feet go behind it)
        mid = top + ih * 9 // 20
        for r, col in ((w * 11 // 20, "#2c58a6"), (w * 8 // 20, "#3466b6")):  # a soft glow behind the character
            cv.create_oval(w // 2 - r, mid - r, w // 2 + r, mid + r, fill=col, width=0)
        if img is not None:
            cv.create_image(w // 2, top, image=img, anchor="n")
        cv.create_rectangle(0, h - plate, w, h, fill="#0c1018", width=0)
        cv.create_rectangle(0, h - plate, w, h - plate + px(3), fill=ui.ACCENT, width=0)
        name, _, form = self.names[base].partition(" – ")
        ch = self.ch()
        if ch.get("menuName"):
            name, form = ch["menuName"], ch.get("menuForm", form)
        cv.create_text(px(16), h - plate + px(14), text=name, anchor="nw", fill=ui.TEXT, font=ui.PLATE,
                       width=w - px(28))
        cv.create_text(px(16), h - plate + px(44), text=form or " ", anchor="nw", fill=ui.ACCENT_HI, font=ui.BOLD,
                       width=w - px(28))

    # ---- pages: made once, then filled for each character -------------------------------------------------------
    def _page(self):
        return self.current

    def _build_page(self, name):
        """Makes page `name` the first time; fills it with the selected character when it does not show it yet.
        Only the page on screen is filled at each click: the others wait until they are shown."""
        if self.chara is None:
            return
        if name not in self.built:
            self.built.add(name)
            self.building = name
            {"Personnage": self._page_identity, "Attaques": self._page_attacks, "Stats": self._page_stats,
             "Rafales de ki": self._page_kiblasts, "Déplacements": self._page_moves}[name](self.pages[name].inner)
            self.building = None
            self.stale.add(name)
        if name not in self.stale:
            return
        self.stale.discard(name)
        was, self.loading = self.loading, True
        for row in self.rows.values():
            if row.page == name:
                row.show(self.value(row.f.key))
        if name == "Personnage":
            self._refresh_identity()
        elif name == "Attaques":
            self._refresh_attacks()
        self.loading = was

    def _refresh_pages(self):
        """What the pages show changed (pictures arrived, a copy, a graft...): the page on screen again now."""
        self.stale = set(self.built)
        self._build_page(self._page())

    def _rows(self, parent, keys, cols=1, labels=None):
        grid = ttk.Frame(parent, style="Card.TFrame")
        grid.pack(anchor="w", fill="x")
        for i, key in enumerate(keys):
            r = FieldRow(self, grid, fields.BY_KEY[key], label=(labels or {}).get(key))
            r.grid(i // cols, i % cols)
        return grid

    def _pick(self, title, current=None, allow_none=None, exclude=()):
        names = [self.target_text(k) for k in range(game.CHARA_COUNT)]
        icons = {k: self.icon(k) for k in range(game.CHARA_COUNT) if self.icon(k) is not None}
        return ui.pick(self, title, names, icons, allow_none=allow_none, current=current, exclude=exclude)

    # -- Personnage: copy of another character, menu names, transformations, forms of the grid cell
    def _page_identity(self, inner):
        """Every widget keeps its place from one character to another (texts change, nothing appears or goes):
        Tk lays out a page again when something moves, and that is what makes a click slow."""
        w = self.idw = {}
        box = ui.card(inner, "Remplacer ce personnage", "un nouveau personnage à cette place", accent=True)
        w["base_hint"] = ui.note(box, 3)
        row = ttk.Frame(box, style="Card.TFrame")
        row.pack(anchor="w", pady=(px(4), 0))
        w["base"] = CharButton(self, row, "Personne (l'original) — choisir…", self._on_base)
        w["base"].b.pack(side="left")
        w["unbase"] = ttk.Button(row, text="", style="Link.TButton", width=24, command=lambda: self._set_base(None))
        w["unbase"].pack(side="left", padx=px(10))

        box = ui.card(inner, "Nom dans les menus", "écran de sélection")
        grid = ttk.Frame(box, style="Card.TFrame")
        grid.pack(anchor="w")
        self.menu_vars, self.menu_counts, self.menu_current = {}, {}, {}
        for i, (key, label) in enumerate((("menuName", "Nom"), ("menuForm", "Forme"))):
            ttk.Label(grid, text=label, style="Card.TLabel").grid(row=i, column=0, sticky="w", padx=(0, px(10)),
                                                                   pady=px(3))
            var = tk.StringVar()
            ui.entry(grid, var, width=34).grid(row=i, column=1, sticky="w", pady=px(3))
            count = ttk.Label(grid, text="", style="Card.Muted.TLabel", width=40)
            count.grid(row=i, column=2, sticky="w", padx=px(10))
            var.trace_add("write", lambda *a, k=key: self._on_menu_name(k))
            self.menu_vars[key], self.menu_counts[key] = var, count
        ui.hint(box, "Vide = le nom d'origine. 30 caractères au plus ; la police du jeu n'a peut-être pas tous les "
                     "accents.", pady=(4, 0))

        box = ui.card(inner, "Transformations en combat", "R3 pendant le combat")
        ui.hint(box, "R3 seul prend la première transformation de la liste ; R3 + une direction prend celle de cette "
                     "direction (relâche R3 en gardant la direction). Le personnage visé doit être débloqué dans la "
                     "sauvegarde. Le coût est en barres de blast.")
        grid = ttk.Frame(box, style="Card.TFrame")
        grid.pack(anchor="w")
        self.tr_rows = []
        for i, key in enumerate(TRANSFORM_KEYS):
            ttk.Label(grid, text=key, style="Card.TLabel").grid(row=i, column=0, sticky="w", padx=(0, px(12)),
                                                                 pady=px(3))
            btn = CharButton(self, grid, "aucune — choisir…", lambda i=i: self._on_transform_pick(i))
            btn.b.grid(row=i, column=1, sticky="w", pady=px(3))
            # the cost and the remove button sit in a box of a fixed size: shown or not, nothing else moves
            extra = ttk.Frame(grid, style="Card.TFrame", width=px(150), height=px(34))
            extra.grid(row=i, column=2, sticky="w", padx=(px(12), 0))
            extra.pack_propagate(False)
            cost = tk.StringVar()
            inner_box = ttk.Frame(extra, style="Card.TFrame")
            ttk.Label(inner_box, text="coût", style="Card.Muted.TLabel").pack(side="left", padx=(0, px(4)))
            ttk.Spinbox(inner_box, from_=0, to=forms.MAX_COST, textvariable=cost, width=3, state="readonly",
                        command=lambda i=i: self._on_transform_cost(i)).pack(side="left")
            rm = ttk.Button(inner_box, text="✕", style="Icon.TButton", width=2,
                            command=lambda i=i: self._set_transform(i, None))
            rm.pack(side="left", padx=px(6))
            ui.Tooltip(rm, "Retirer cette transformation")
            self.tr_rows.append({"btn": btn, "extra": inner_box, "cost": cost})
        w["tr_note"] = ui.note(box, 2)
        w["tr_auto"] = ttk.Button(box, text="", style="Link.TButton", width=40,
                                  command=lambda: self._reset_auto("transforms"))
        w["tr_auto"].pack(anchor="w")

        box = ui.card(inner, "Formes à l'écran de sélection", "les choix dans la case de la grille")
        w["forms_hint"] = ui.note(box, 2)
        grid = ttk.Frame(box, style="Card.TFrame")
        grid.pack(anchor="w")
        self.form_rows = []
        for k in range(forms.MAX_FORMS):
            num = ttk.Label(grid, text=f"{k + 1}.", style="Card.Muted.TLabel")
            num.grid(row=k, column=0, sticky="e", padx=(0, px(8)), pady=px(2))
            btn = CharButton(self, grid, "", (lambda k=k: self._on_form_pick(k)) if k else None)
            btn.b.grid(row=k, column=1, sticky="w", pady=px(2))
            rm = ttk.Button(grid, text="", style="Icon.TButton", width=2, command=lambda k=k: self._set_form(k, None))
            rm.grid(row=k, column=2, padx=px(6))
            if k:
                ui.Tooltip(rm, "Retirer cette forme de la case")
            self.form_rows.append((btn, rm))
        w["forms_auto"] = ttk.Button(box, text="", style="Link.TButton", width=40,
                                     command=lambda: self._reset_auto("forms"))
        w["forms_auto"].pack(anchor="w", pady=(px(6), 0))

    def _refresh_identity(self):
        w, c, ch = self.idw, self.chara, self.ch()
        base = int(ch["base"]) if "base" in ch else None
        w["base_hint"].configure(text=f"Le personnage choisi prend la place de {self.names[c]} tout entier : modèle, "
                                      "attaques, voix, portraits et nom dans les menus. L'original n'est plus jouable "
                                      "tant que le pack est appliqué. Les réglages des autres onglets partent du "
                                      "personnage choisi.")
        w["base"].set(base)
        w["unbase"].configure(text="Retirer le remplacement" if base is not None else "",
                              state="normal" if base is not None else "disabled")

        own_name, own_form = self.names[base if base is not None else c].partition(" – ")[::2]
        self.menu_current = {"menuName": own_name, "menuForm": own_form}
        for key, var in self.menu_vars.items():
            var.set(ch.get(key, ""))
            self._menu_count(key)

        try:
            slots = self.game.transforms(c, ch, self.pack)
        except game.ModError:
            slots = forms.read(self.game.params(base if base is not None else c))
        for i, r in enumerate(self.tr_rows):
            s = slots[i]
            r["btn"].set(None if s is None else s["to"])
            if s is not None:
                r["cost"].set(str(s["cost"]))
                r["extra"].pack(side="left", fill="y")
            else:
                r["extra"].pack_forget()
        explicit = ch.get("transforms") is not None
        w["tr_note"].configure(text="" if explicit or base is None else
                               "Automatique : celles du personnage copié, dirigées vers les copies de ce pack quand il "
                               "y en a (une copie de Vegeta devient la copie de Super Vegeta).")
        w["tr_auto"].configure(text="Revenir aux transformations automatiques" if explicit else "",
                               state="normal" if explicit else "disabled")

        if "grid" not in self.game._cache and menunames.cached(self.game.root, game.tool_folder()) is None:
            w["forms_hint"].configure(text="Lecture de la grille du jeu… (une seule fois)")
            shown, editable = [], False
        elif self.game.heads_cell(c):
            w["forms_hint"].configure(text="Quand on choisit cette case, on choisit ensuite une de ces formes pour "
                                           "commencer le combat (7 au plus). La première est toujours ce personnage.")
            shown, editable = self._current_forms(), True
        else:  # a form of another cell: that cell's forms, to look at
            cell = next((cell for cell in self.game.grid() if c in forms.cell_forms(cell)), None)
            w["forms_hint"].configure(
                text=f"Ce personnage n'a pas sa propre case : c'est une des formes de la case de "
                     f"{self.names[cell[0]]} (ci-dessous). Change les formes depuis ce personnage-là." if cell else
                     "Ce personnage n'est pas dans la grille de sélection.")
            shown, editable = (forms.cell_forms(cell) if cell else []), False
        for k, (btn, rm) in enumerate(self.form_rows):
            if k < len(shown):
                btn.set(shown[k], active=editable and k > 0)
                rm.configure(text="✕" if editable and k else "", state="normal" if editable and k else "disabled")
            else:
                add = editable and k == len(shown)
                btn.set(None, none_text="＋  ajouter une forme" if add else "", active=add, ghost=not add)
                rm.configure(text="", state="disabled")
        auto = editable and bool(ch.get("forms"))
        w["forms_auto"].configure(text="Revenir aux formes automatiques" if auto else "",
                                  state="normal" if auto else "disabled")

    def _on_base(self):
        c = self.chara
        cur = int(self.ch()["base"]) if "base" in self.ch() else None
        new = self._pick(f"Mettre un personnage à la place de {self.names[c]}", current=cur,
                         allow_none="Garder l'original", exclude=(c,))
        if new is None:
            return
        self._set_base(None if new == ui.Picker.NONE else new)

    def _set_base(self, new):
        ch = modpack.chara(self.pack, self.chara)
        old = int(ch["base"]) if "base" in ch else None
        if new == old:
            return
        if (ch.get("fields") or any(ch.get("texts", {}).values()) or ch.get("transplants")
                or ch.get("transforms") is not None or ch.get("forms")) and not messagebox.askyesno(
                TITLE, "Les réglages déjà faits pour cet emplacement (valeurs, noms d'attaques, attaques reprises, "
                       "transformations, formes) seront effacés : ils valaient pour l'ancien personnage. Continuer ?"):
            return
        ch["fields"], ch["texts"] = {}, {}
        for k in ("transplants", "transforms", "forms"):
            ch.pop(k, None)
        if new is None:
            ch.pop("base", None)
        else:
            ch["base"] = new
        self._reselect()
        self.status.set(f"{self.names[self.chara]} : " + ("emplacement d'origine" if new is None else
                                                          f"remplacé par {self.names[new]}"))

    def _menu_count(self, key):
        n = len(self.menu_vars[key].get())
        self.menu_counts[key].configure(text=(f"{n}/30" if n else f"d'origine : {self.menu_current[key] or '—'}"),
                                        foreground="#ff6b6b" if n > 30 else ui.MUTED)

    def _on_menu_name(self, key):
        self._menu_count(key)
        if self.loading:
            return
        text = self.menu_vars[key].get()
        ch = modpack.chara(self.pack, self.chara)
        if text.strip() and len(text) <= 30:
            ch[key] = text.strip()
        else:
            ch.pop(key, None)
        self._refresh_row()
        self._draw_portrait()

    def _current_transforms(self):
        try:
            return forms.chosen(self.game.transforms(self.chara, self.ch(), self.pack))
        except game.ModError:
            return [None] * forms.SLOTS

    def _set_transform(self, i, value):
        t = self._current_transforms()
        t[i] = value
        modpack.chara(self.pack, self.chara)["transforms"] = t
        self._reselect()

    def _on_transform_pick(self, i):
        cur = self._current_transforms()[i]
        new = self._pick(f"Transformation {TRANSFORM_KEYS[i].strip()}", current=None if cur is None else cur["to"],
                         allow_none="Aucune")
        if new is None:
            return
        self._set_transform(i, None if new == ui.Picker.NONE else {"to": new, "cost": cur["cost"] if cur else 1})

    def _on_transform_cost(self, i):
        cur = self._current_transforms()[i]
        if cur is not None and not self.loading:
            self._set_transform(i, {"to": cur["to"], "cost": int(self.tr_rows[i]["cost"].get() or 0)})

    def _current_forms(self):
        try:
            f = self.game.grid_forms(self.chara, self.ch(), self.pack)
        except game.ModError:
            f = None
        return f if f is not None else forms.cell_forms(forms.cell_of(self.game.grid(), self.chara))

    def _set_form(self, k, value):
        f = self._current_forms()
        if value is None:
            del f[k]
        elif k < len(f):
            f[k] = value
        else:
            f.append(value)
        out = []
        for x in f:
            if x not in out:
                out.append(x)
        modpack.chara(self.pack, self.chara)["forms"] = out
        self._reselect()

    def _on_form_pick(self, k):
        cur = self._current_forms()
        new = self._pick(f"Forme n°{k + 1} de la case", current=cur[k] if k < len(cur) else None)
        if new is not None and new != ui.Picker.NONE:
            self._set_form(k, new)

    def _reset_auto(self, key):
        modpack.chara(self.pack, self.chara).pop(key, None)
        self._reselect()

    # -- Attaques: each special move with its name, the attack it may take from another character, its values
    def _page_attacks(self, inner):
        box = ui.card(inner, "Changer une attaque", "Blast 1, Blast 2 et Ultime")
        ui.hint(box, "Pour donner à ce personnage l'attaque d'un autre : dans sa fiche ci-dessous, clique sur "
                     "« Remplacer par », choisis le personnage, puis laquelle de ses attaques. Toute l'attaque vient "
                     "avec : animation, effets, valeurs et nom (les voix restent celles du personnage). Un Blast 1 se "
                     "remplace par un Blast 1 ; un Blast 2 ou l'Ultime par un Blast 2 ou un Ultime.", pady=(0, 0))
        self.atk_cards, self.name_vars = [], {}
        for title, prefix, slot, idx in SPECIALS:
            box = ui.card(inner, title, "", accent=(prefix == "super" and slot == 2))
            kind = "skill" if prefix == "skill" else "super"
            card = {"box": box, "idx": idx, "kind": kind, "slot": slot}
            self._name_row(box, idx)
            row = ttk.Frame(box, style="Card.TFrame")
            row.pack(anchor="w", pady=(px(2), px(2)))
            ttk.Label(row, text="Remplacer par", style="Card.TLabel", width=16).pack(side="left")
            card["btn"] = CharButton(self, row, "garder la sienne — choisir…",
                                     lambda k=kind, s=slot: self._on_graft_pick(k, s), width=30)
            card["btn"].b.pack(side="left")
            # the attack list and the remove button in a box of a fixed size (nothing moves when they show)
            extra = ttk.Frame(row, style="Card.TFrame", width=px(330), height=px(40))
            extra.pack(side="left", padx=(px(8), 0))
            extra.pack_propagate(False)
            card["extra"] = ttk.Frame(extra, style="Card.TFrame")
            card["combo"] = ttk.Combobox(card["extra"], width=30, state="readonly")
            card["combo"].pack(side="left")
            card["combo"].bind("<<ComboboxSelected>>", lambda e, k=kind, s=slot: self._on_graft_attack(k, s))
            rm = ttk.Button(card["extra"], text="✕", style="Icon.TButton", width=2,
                            command=lambda k=kind, s=slot: self._set_graft(k, s, None))
            rm.pack(side="left", padx=px(4))
            ui.Tooltip(rm, "Garder l'attaque d'origine")
            keys = [f.key for f in fields.FIELDS if f.key.startswith(prefix + ".") and f.key.endswith("." + str(slot))]
            ttk.Frame(box, style="Card.TFrame", height=px(6)).pack()
            self._rows(box, keys, cols=1)
            self.atk_cards.append(card)
        box = ui.card(inner, "Autres noms de la liste des commandes", "menu pause")
        self._name_row(box, 5, label="Hyper Smash")

    def _name_row(self, box, idx, label="Nom affiché"):
        row = ttk.Frame(box, style="Card.TFrame")
        row.pack(anchor="w", pady=(0, px(4)))
        ttk.Label(row, text=label, style="Card.TLabel", width=16).pack(side="left")
        for lang, lang_name in NAME_LANGS:
            var = tk.StringVar()
            e = ui.entry(row, var, width=24)
            e.pack(side="left", padx=(0, px(4)))
            ttk.Label(row, text=lang.upper(), style="Card.Muted.TLabel").pack(side="left", padx=(0, px(14)))
            item = {"var": var, "entry": e, "orig": "", "lang_name": lang_name}
            ui.Tooltip(e, lambda it=item: f"{it['lang_name']} — d'origine : {it['orig'].strip()}")
            var.trace_add("write", lambda *a, l=lang, i=idx: self._on_name(l, i))
            self.name_vars[(lang, idx)] = item

    def _grafts(self):
        """{(kind, slot): graft} of the selected character."""
        return {("skill" if transplant.is_skill(t) else "super", int(t["slot"])): t
                for t in self.ch().get("transplants", [])}

    def _attack_choices(self, kind, src):
        if kind == "skill":
            names = (self.game.move_names(src) + ["", ""])[:2]
            return [f"{fields.SKILL_SLOTS[k]} : {names[k].strip() or '?'}" for k in range(2)]
        tech = self.game.technique_names(src)
        return [f"{fields.SUPER_SLOTS[k]} : {tech[k] or '?'}" for k in range(3)]

    def _refresh_attacks(self):
        c, ch = self.chara, self.ch()
        names = {lang: self.game.start_move_names(c, ch, lang) for lang, _ in NAME_LANGS}
        renames = ch.get("texts", {})
        for (lang, idx), item in self.name_vars.items():
            orig = names[lang][idx] if idx < len(names[lang]) else ""
            item["orig"] = orig
            item["var"].set(renames.get(lang, {}).get(str(idx), orig))
            self._paint_name(item["entry"], item["var"].get() != orig)
        grafts = self._grafts()
        for card in self.atk_cards:
            idx = card["idx"]
            card["box"].sub.configure(text=names["en"][idx].strip() if idx < len(names["en"]) else "")
            t = grafts.get((card["kind"], card["slot"]))
            card["btn"].set(int(t["from"]) if t else None)
            if t:
                card["combo"].configure(values=self._attack_choices(card["kind"], int(t["from"])))
                card["combo"].current(int(t["fromSlot"]))
                card["extra"].pack(side="left", fill="y")
            else:
                card["extra"].pack_forget()

    @staticmethod
    def _paint_name(e, changed):
        e.configure(bg=ui.MOD_BG if changed else ui.FIELD, fg=ui.MOD_TEXT if changed else ui.TEXT)

    def _on_name(self, lang, i):
        if self.loading:
            return
        item = self.name_vars[(lang, i)]
        texts = modpack.chara(self.pack, self.chara).setdefault("texts", {}).setdefault(lang, {})
        name = item["var"].get()
        if name.strip() and name != item["orig"]:
            texts[str(i)] = name
        else:
            texts.pop(str(i), None)
        self._paint_name(item["entry"], str(i) in texts)
        self._refresh_row()

    def _on_graft_pick(self, kind, slot):
        cur = self._grafts().get((kind, slot))
        what = (fields.SKILL_SLOTS if kind == "skill" else fields.SUPER_SLOTS)[slot]
        new = self._pick(f"Remplacer le {what} par l'attaque d'un autre personnage",
                         current=int(cur["from"]) if cur else None, allow_none="Garder la sienne")
        if new is None:
            return
        if new == ui.Picker.NONE:
            self._set_graft(kind, slot, None)
        else:
            self._set_graft(kind, slot, new, int(cur["fromSlot"]) if cur else slot)

    def _on_graft_attack(self, kind, slot):
        cur = self._grafts().get((kind, slot))
        card = next(c for c in self.atk_cards if c["kind"] == kind and c["slot"] == slot)
        if cur is not None:
            self._set_graft(kind, slot, int(cur["from"]), card["combo"].current())

    def _set_graft(self, kind, slot, src, from_slot=None):
        """Takes attack from_slot of character src as this character's attack `slot` (kind "skill": a Blast 1, else
        a Blast 2 / the Ultimate); src None: keeps its own."""
        ch = modpack.chara(self.pack, self.chara)
        old = ch.get("transplants")
        grafts = [t for k, t in self._grafts().items() if k != (kind, slot)]
        if src is not None:
            t = {"slot": slot, "from": src, "fromSlot": from_slot}
            if kind == "skill":
                t = dict(kind="skill", **t)
            grafts.append(t)
            grafts.sort(key=lambda g: (transplant.is_skill(g), int(g["slot"])))
            problem = self.game.graft_conflict(self.chara, dict(ch, transplants=grafts), t)
            if problem:
                messagebox.showwarning(TITLE, problem)
                if old is not None:
                    ch["transplants"] = old
                self._refresh_pages()  # (the attack list shows the graft that stays)
                return
        if grafts:
            ch["transplants"] = grafts
        else:
            ch.pop("transplants", None)
        self._reselect()  # (the starting values and the move names follow the grafted attacks)


    # -- Stats, Rafales de ki, Déplacements: only the values change from one character to another
    def _page_stats(self, inner):
        for title, sub, keys in (
                ("Vie, ki et blast stocks", "10 000 = 1 barre de vie · 20 000 = 1 barre de ki",
                 ["roster.health", "roster.kiStart", "roster.stocks"]),
                ("Résistance", None, ["param.damageTaken", "param.hitReactScale"]),
                ("Corps à corps", None, ["melee.damageScale"]),
                ("Ki et Max Power", None, [f.key for f in fields.FIELDS if f.slot == "Ki et Max Power"])):
            box = ui.card(inner, title, sub)
            self._rows(box, keys)

    def _page_kiblasts(self, inner):
        box = ui.card(inner, "Rafales de ki", "10 000 = 1 barre de vie · 20 000 = 1 barre de ki")
        ui.hint(box, "Passe la souris sur une case pour voir son unité et sa valeur d'origine ; clic droit pour la "
                     "remettre.")
        grid = ttk.Frame(box, style="Card.TFrame")
        grid.pack(anchor="w")
        for j, (_, label) in enumerate(KIBLAST_COLS):
            ttk.Label(grid, text=label, style="Card.Muted.TLabel").grid(row=0, column=j + 1, pady=(0, px(2)))
        for k, kname in enumerate(fields.KIBLAST_NAMES):
            ttk.Label(grid, text=kname, style="Card.TLabel").grid(row=k + 1, column=0, sticky="w", padx=(0, px(12)))
            for j, (name, _) in enumerate(KIBLAST_COLS):
                FieldRow(self, grid, fields.BY_KEY[f"kiblast.{name}.{k}"], compact=True).grid(k + 1, j + 1)

    def _page_moves(self, inner):
        box = ui.card(inner, "Vitesses de déplacement", "x10 km/h")
        ui.hint(box, "Le rôle exact de chacune des 20 vitesses n'est pas encore identifié. Pour un personnage plus "
                     "rapide ou plus lent, change-les toutes du même pourcentage :")
        row = ttk.Frame(box, style="Card.TFrame")
        row.pack(anchor="w", pady=(0, px(10)))
        pct = tk.StringVar(value="120")
        ttk.Label(row, text="Tout multiplier par", style="Card.TLabel").pack(side="left")
        ui.entry(row, pct, width=6, justify="right").pack(side="left", padx=px(6))
        ttk.Label(row, text="%", style="Card.TLabel").pack(side="left")
        ttk.Button(row, text="Appliquer", style="Small.TButton",
                   command=lambda: self._scale_moves(pct.get())).pack(side="left", padx=px(10))
        ttk.Button(row, text="Tout remettre d'origine", style="Link.TButton",
                   command=lambda: self._scale_moves(None)).pack(side="left")
        keys = [f"move.speed.{i}" for i in range(20)]
        self._rows(box, keys, cols=2, labels={k: f"Vitesse {i + 1}" for i, k in enumerate(keys)})

    def _scale_moves(self, pct):
        try:
            p = None if pct is None else float(str(pct).replace(",", ".")) / 100
        except ValueError:
            self.status.set(f"« {pct} » n'est pas un pourcentage")
            return
        for i in range(20):
            row = self.rows.get(f"move.speed.{i}")
            if row:
                o = self.orig[row.f.key]
                row.var.set(fmt(row.f, o if p is None else row.f.clamp(o * p)))

    # ---- editing values ----------------------------------------------------------------------------------------
    def on_field(self, row):
        if self.loading:
            return
        f = row.f
        text = row.var.get().strip().replace(",", ".")
        try:
            v = float(text)
            if not f.is_float:
                v = int(round(v))
        except ValueError:
            row.paint(bad=True)
            self.status.set(f"« {text} » n'est pas un nombre")
            return
        if f.clamp(v) != v:
            row.paint(bad=True)
            self.status.set(f"{f.label} : entre {fmt(f, f.lo)} et {fmt(f, f.hi)}")
            return
        values = modpack.chara(self.pack, self.chara)["fields"]
        o = self.orig[f.key]
        if (abs(v - o) < 1e-4) if f.is_float else v == o:
            values.pop(f.key, None)
        else:
            values[f.key] = v
        row.paint(v)
        self._refresh_row()
        m = meaning(f, v)
        self.status.set(f"{f.slot} — {f.label} : {fmt(f, v)}" + (f"  ({m})" if m else ""))

    def _on_nick(self):
        if self.loading:
            return
        ch = modpack.chara(self.pack, self.chara)
        if self.nick_var.get().strip():
            ch["nickname"] = self.nick_var.get().strip()
        else:
            ch.pop("nickname", None)
        self._refresh_row()

    def reset_chara(self):
        if self.is_changed(self.chara) and not messagebox.askyesno(
                TITLE, f"Effacer tous les changements de {self.names[self.chara]} dans ce pack ?"):
            return
        self.pack["characters"].pop(str(self.chara), None)
        self._reselect()

    # ---- packs and the game ------------------------------------------------------------------------------------
    def _snapshot(self):
        self._sync_meta()
        return json.dumps(modpack.clean(json.loads(json.dumps(self.pack))), sort_keys=True)

    def _dirty(self):
        snap = self._snapshot()
        self.title(f"{TITLE} — {self.pack['name']}" + (" *" if snap != getattr(self, "saved", snap) else ""))
        if self.applied is None and not any(self.is_changed(c) for c in range(game.CHARA_COUNT)):
            self.state_lbl.configure(text="", style="Panel.Muted.TLabel")
        elif snap == self.applied:
            self.state_lbl.configure(text="✓ Appliqué", style="Good.Panel.TLabel")
        else:
            self.state_lbl.configure(text="● Non appliqué", style="Warn.Panel.TLabel")

    def _sync_meta(self):
        self.pack["name"] = self.pack_name.get().strip() or "Sans nom"
        self.pack["author"] = self.pack_author.get().strip()

    def _keep_changes(self):
        """When the pack has changes not saved: asks whether to save them first. False = the person cancelled."""
        if self._snapshot() == self.saved:
            return True
        answer = messagebox.askyesnocancel(TITLE, f"Le pack « {self.pack['name']} » a des changements qui ne sont "
                                                  "pas enregistrés. Les enregistrer d'abord ?")
        if answer is None:
            return False
        return self.save_pack() if answer else True

    def quit_app(self):
        if self._keep_changes():
            self.destroy()

    def new_pack(self):
        if not self._keep_changes():
            return
        self.pack = modpack.new()
        self.pack_path = None
        self.pack_name.set(self.pack["name"])
        self.pack_author.set("")
        self.saved = self._snapshot()
        self.refresh_list()
        self._reselect()

    def share_pack(self):
        """The pack as a code to copy, and a box to load a friend's code."""
        self._sync_meta()
        self.share_dialog = ui.ShareDialog(self, modpack.to_code(self.pack), modpack.fingerprint(self.pack),
                                        self._load_code)

    def _load_code(self, text):
        """Loads the pack of a pasted code; None, or what is wrong with the code."""
        try:
            pack = modpack.from_code(text)
        except ValueError as e:
            return str(e)
        if not self._keep_changes():
            return "Chargement annulé."
        self.pack = pack
        self.pack_path = None
        self.pack_name.set(pack.get("name", ""))
        self.pack_author.set(pack.get("author", ""))
        self.saved = self._snapshot()
        self.refresh_list()
        self._reselect()
        self.status.set(f"Pack « {pack.get('name', '')} » chargé depuis un code "
                        f"({len(pack['characters'])} personnage(s) modifié(s), empreinte {modpack.fingerprint(pack)}). "
                        "« Appliquer au jeu » pour y jouer.")
        return None

    def open_pack(self):
        if not self._keep_changes():
            return
        path = filedialog.askopenfilename(title="Ouvrir un pack", filetypes=[("Pack BT3 Mod Studio", "*.bt3mod.json"),
                                                                            ("JSON", "*.json")])
        if not path:
            return
        try:
            self.pack = modpack.load(path)
        except (OSError, ValueError) as e:
            messagebox.showerror(TITLE, f"Impossible d'ouvrir ce pack :\n{e}")
            return
        self.pack_path = path
        name, author = self.pack.get("name", ""), self.pack.get("author", "")
        self.pack_name.set(name)
        self.pack_author.set(author)
        self.saved = self._snapshot()
        self.refresh_list()
        self._reselect()
        self.status.set(f"Pack ouvert : {path} ({len(self.pack['characters'])} personnage(s) modifié(s))")

    def save_pack(self):
        """Saves the pack in a file chosen by the person; True when saved."""
        self._sync_meta()
        folder = os.path.dirname(self.pack_path) if self.pack_path else os.path.join(game.tool_folder(), "packs")
        path = filedialog.asksaveasfilename(title="Enregistrer le pack", defaultextension=".bt3mod.json",
                                            initialdir=folder if os.path.isdir(folder) else None,
                                            initialfile=(self.pack["name"] or "pack") + ".bt3mod.json",
                                            filetypes=[("Pack BT3 Mod Studio", "*.bt3mod.json")])
        if not path:
            return False
        modpack.save(self.pack, path)
        self.pack_path = path
        self.saved = self._snapshot()
        self._dirty()
        self.status.set(f"Pack enregistré : {path} — envoie ce fichier à tes amis pour jouer avec les mêmes mods")
        return True

    def apply(self):
        """Writes the pack into the game, in a thread: the first pack that touches the menus has the tool read the
        game's menu archives once (about a minute and a half; kept for later)."""
        if getattr(self, "_applying", False):
            return
        self._sync_meta()
        modpack.clean(self.pack)
        n_chara = len(self.pack["characters"])
        needs_menus = any("base" in ch or ch.get("menuName") or ch.get("menuForm") or ch.get("forms")
                          for ch in self.pack["characters"].values())
        first_time = needs_menus and menunames.cached(self.game.root, game.tool_folder()) is None
        self.status.set("Application du pack…" + (" Première fois avec des noms ou des remplacements : l'outil lit "
                                                  "les menus du jeu (environ 1 min 30, une seule fois)." if first_time else ""))
        self.config(cursor="watch")
        self._applying = True
        result = {}
        snap = self._snapshot()

        def work():
            try:
                result["n"] = self.game.apply(self.pack)
            except game.ModError as e:
                result["error"] = str(e)
            except Exception as e:  # (shown to the user rather than lost in the thread)
                result["error"] = f"Erreur inattendue : {e}"

        def done():
            if thread.is_alive():
                self.after(200, done)
                return
            self._applying = False
            self.config(cursor="")
            if "error" in result:
                self.status.set("Échec de l'application")
                messagebox.showerror(TITLE, result["error"])
                return
            self.applied = snap
            self.refresh_list()
            self._dirty()
            self.status.set(f"Appliqué au jeu : {result['n']} fichier(s) — empreinte {modpack.fingerprint(self.pack)}")
            messagebox.showinfo(TITLE, f"Pack « {self.pack['name']} » appliqué : {n_chara} personnage(s), "
                                       f"{result['n']} fichier(s) écrits dans gamedata/mods.\n\n"
                                       "Lance (ou relance) le jeu pour en profiter.")

        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        self.after(200, done)

    def remove_mods(self):
        if not messagebox.askyesno(TITLE, "Retirer du jeu tous les fichiers écrits par BT3 Mod Studio ?\n"
                                          "(Ton pack reste ouvert ici, rien n'est perdu.)"):
            return
        n = self.game.remove()
        self.applied = None
        self._dirty()
        messagebox.showinfo(TITLE, f"{n} fichier(s) retiré(s). Le jeu est revenu à l'original.")


def main():
    try:  # sharp text on screens with a zoom above 100 % (the sizes follow: studio_ui.px)
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    gamedata = game.find_gamedata(sys.argv[1] if len(sys.argv) > 1 else None)
    if gamedata is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(TITLE, "Choisis le dossier du jeu Tenkaichi3Decomp (celui qui contient "
                                   "Tenkaichi3Decomp.exe et le dossier « gamedata »).")
        d = filedialog.askdirectory(title="Dossier du jeu Tenkaichi3Decomp")
        gamedata = game.find_gamedata(d) if d else None
        if gamedata is None:
            if d:
                messagebox.showerror(TITLE, "Je ne trouve pas les données du jeu dans ce dossier.")
            root.destroy()
            return
        root.destroy()
        game.remembered_gamedata(gamedata)  # (asked only once)
    Studio(gamedata).mainloop()


if __name__ == "__main__":
    main()
