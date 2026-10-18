"""The look of BT3 Mod Studio: colours, fonts, ttk styles, and the widgets the window is made of (scrolling pages,
cards, value fields, character buttons, the character picker, tooltips)."""
import tkinter as tk
from tkinter import ttk

# ---- palette -----------------------------------------------------------------------------------------------------
BG = "#12151d"          # window
PANEL = "#191e29"       # side bar, top bar
CARD = "#202737"        # cards
FIELD = "#2a3246"       # inputs
FIELD_HI = "#34405a"    # inputs under the mouse
BORDER = "#323c54"
TEXT = "#e8ecf4"
MUTED = "#a3adc2"       # (6:1 on the cards: readable small text)
ACCENT = "#ff8c1a"      # Goku's gi
ACCENT_HI = "#ffa54a"
ACCENT_DK = "#cf6c0a"
INK = "#1b1104"         # text on the accent colour
SELECT = "#2c3b5c"      # selected row
MOD_BG = "#4b3a12"      # a changed value
MOD_TEXT = "#ffd27a"
BAD_BG = "#5c1f27"      # a value that cannot be taken
GOOD = "#4cc38a"
SKY_TOP, SKY_BOTTOM = "#2b55a0", "#141c2e"   # behind the character's picture

S = 1.0                 # screen pixels per 1/96 inch (set by setup)
Z = 1.0                 # the person's text size (1 = normal; set_zoom)
ZOOMS = (0.9, 1.0, 1.1, 1.25, 1.4, 1.6)


def px(n):
    return int(round(n * S))


def pz(n):
    """px for a size that follows the text size."""
    return int(round(n * S * Z))


# The fonts are named Tk fonts: a change of the text size changes them, and every widget follows.
FONT_SPECS = {"FONT": ("Segoe UI", 10), "SMALL": ("Segoe UI", 9), "BOLD": ("Segoe UI Semibold", 10),
              "SECTION": ("Segoe UI Semibold", 12), "TITLE": ("Segoe UI Semibold", 19),
              "APP_TITLE": ("Segoe UI Semibold", 14), "PLATE": ("Segoe UI Semibold", 13), "MONO": ("Consolas", 9)}
FONT, SMALL, BOLD, SECTION, TITLE, APP_TITLE, PLATE, MONO = FONT_SPECS.values()  # (named by setup)
_fonts = {}
_fonts_root = None


def _make_fonts(root):
    import tkinter.font as tkfont
    global _fonts_root
    if root is not None and root is not _fonts_root:  # (a new window: a new Tk, its own fonts)
        _fonts.clear()
        _fonts_root = root
    for name, (family, size) in FONT_SPECS.items():
        if name not in _fonts:
            _fonts[name] = tkfont.Font(root, name="bt3" + name.lower(), family=family, size=size)
        _fonts[name].configure(size=max(7, int(round(size * Z))))
        globals()[name] = _fonts[name].name


def set_zoom(z):
    """Another text size: the fonts change at once (the sizes made with pz follow when a page is made again)."""
    global Z
    Z = z
    _make_fonts(None)


def text_lines(font, text, width):
    """How many lines Tk needs for `text` wrapped at `width` pixels."""
    f = next((x for x in _fonts.values() if x.name == font), None)
    if f is None:
        return text.count("\n") + 1
    n = 0
    for para in text.split("\n"):
        n += 1
        line = ""
        for word in para.split(" "):
            cand = word if not line else line + " " + word
            if not line or f.measure(cand) <= width:
                line = cand
            else:
                n += 1
                line = word
    return n


def setup(root, zoom=1.0):
    """Makes the fonts and the ttk styles; returns the screen scale."""
    global S, Z
    S = max(1.0, root.winfo_fpixels("1i") / 96.0)
    Z = zoom
    _make_fonts(root)
    root.configure(bg=BG)
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=BG, foreground=TEXT, fieldbackground=FIELD, bordercolor=BORDER, lightcolor=BORDER,
                 darkcolor=BORDER, troughcolor=PANEL, focuscolor=BG, selectbackground=ACCENT, selectforeground=INK,
                 insertcolor=TEXT, font=FONT)
    for name, bg in (("", BG), ("Panel.", PANEL), ("Card.", CARD)):
        st.configure(name + "TFrame", background=bg)
        st.configure(name + "TLabel", background=bg, foreground=TEXT)
        st.configure(name + "Muted.TLabel", background=bg, foreground=MUTED, font=SMALL)
        st.configure(name + "Hint.TLabel", background=bg, foreground=MUTED, font=FONT)
        st.configure(name + "Title.TLabel", background=bg, foreground=TEXT, font=SECTION)
        st.configure(name + "Accent.TLabel", background=bg, foreground=ACCENT, font=BOLD)
        st.configure(name + "TCheckbutton", background=bg, foreground=TEXT, indicatorbackground=FIELD,
                     indicatorforeground=ACCENT, upperbordercolor=BORDER, lowerbordercolor=BORDER)
        st.map(name + "TCheckbutton", background=[("active", bg)], indicatorbackground=[("active", FIELD_HI)])
    st.configure("Big.TLabel", background=BG, foreground=TEXT, font=TITLE)
    st.configure("AppTitle.Panel.TLabel", background=PANEL, foreground=TEXT, font=APP_TITLE)
    st.configure("Good.Panel.TLabel", background=PANEL, foreground=GOOD, font=SMALL)
    st.configure("Warn.Panel.TLabel", background=PANEL, foreground=MOD_TEXT, font=SMALL)
    st.configure("Badge.TLabel", background=MOD_BG, foreground=MOD_TEXT, font=SMALL, padding=(px(8), px(2)))
    st.configure("BadgeBlue.TLabel", background=SELECT, foreground="#b9d1ff", font=SMALL, padding=(px(8), px(2)))

    st.configure("TButton", background=FIELD, foreground=TEXT, bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD,
                 padding=(px(12), px(5)), relief="flat", focusthickness=0)
    st.map("TButton", background=[("disabled", PANEL), ("pressed", BORDER), ("active", FIELD_HI)],
           foreground=[("disabled", MUTED)], lightcolor=[("active", FIELD_HI)], darkcolor=[("active", FIELD_HI)])
    st.configure("Accent.TButton", background=ACCENT, foreground=INK, bordercolor=ACCENT_DK, lightcolor=ACCENT,
                 darkcolor=ACCENT, font=BOLD, padding=(px(16), px(6)))
    st.map("Accent.TButton", background=[("pressed", ACCENT_DK), ("active", ACCENT_HI)],
           lightcolor=[("active", ACCENT_HI)], darkcolor=[("active", ACCENT_HI)])
    st.configure("Small.TButton", padding=(px(8), px(2)), font=SMALL)
    st.configure("Link.TButton", background=CARD, foreground=ACCENT, bordercolor=CARD, lightcolor=CARD,
                 darkcolor=CARD, padding=(px(4), px(1)), font=SMALL)
    st.map("Link.TButton", background=[("active", CARD)], foreground=[("active", ACCENT_HI)],
           lightcolor=[("active", CARD)], darkcolor=[("active", CARD)])
    st.configure("Icon.TButton", background=CARD, foreground=MUTED, bordercolor=CARD, lightcolor=CARD, darkcolor=CARD,
                 padding=(px(4), px(1)), font=FONT)
    st.map("Icon.TButton", background=[("active", FIELD)], foreground=[("active", ACCENT)],
           lightcolor=[("active", FIELD)], darkcolor=[("active", FIELD)])
    st.configure("Char.TButton", background=FIELD, foreground=TEXT, anchor="w", padding=(px(4), px(2)))
    st.configure("Ghost.TButton", background=CARD, foreground=MUTED, bordercolor=CARD, lightcolor=CARD,
                 darkcolor=CARD, anchor="w", padding=(px(4), px(2)))
    st.map("Ghost.TButton", background=[("active", CARD)], lightcolor=[("active", CARD)],
           darkcolor=[("active", CARD)], bordercolor=[("active", CARD)])
    st.configure("Seg.TButton", background=PANEL, foreground=MUTED, bordercolor=BORDER, lightcolor=PANEL,
                 darkcolor=PANEL, padding=(px(10), px(3)), font=SMALL)
    st.map("Seg.TButton", background=[("active", FIELD)], foreground=[("active", TEXT)])
    st.configure("SegOn.TButton", background=FIELD_HI, foreground=TEXT, bordercolor=ACCENT, lightcolor=FIELD_HI,
                 darkcolor=FIELD_HI, padding=(px(10), px(3)), font=SMALL)

    st.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT, bordercolor=BORDER,
                 lightcolor=FIELD, darkcolor=FIELD, padding=px(4))
    st.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", FIELD)])
    st.configure("Search.TEntry", padding=(px(8), px(6)))
    st.configure("TCombobox", fieldbackground=FIELD, background=FIELD, foreground=TEXT, arrowcolor=MUTED,
                 bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD, padding=px(4), arrowsize=px(12))
    st.map("TCombobox", fieldbackground=[("readonly", FIELD), ("disabled", PANEL)],
           foreground=[("readonly", TEXT), ("disabled", MUTED)], selectbackground=[("readonly", FIELD)],
           selectforeground=[("readonly", TEXT)], arrowcolor=[("active", ACCENT)], background=[("active", FIELD_HI)],
           bordercolor=[("focus", ACCENT)])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", INK)
    root.option_add("*TCombobox*Listbox.font", FONT)
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    st.configure("TSpinbox", fieldbackground=FIELD, background=FIELD, foreground=TEXT, arrowcolor=MUTED,
                 bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD, padding=px(3), arrowsize=px(11))
    st.map("TSpinbox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", TEXT)],
           arrowcolor=[("active", ACCENT)], selectbackground=[("readonly", FIELD)],
           selectforeground=[("readonly", TEXT)])

    st.configure("Tab.TButton", background=BG, foreground=MUTED, bordercolor=BG, lightcolor=BG, darkcolor=BG,
                 padding=(px(18), px(8)), font=BOLD)
    st.map("Tab.TButton", background=[("active", PANEL)], foreground=[("active", TEXT)],
           lightcolor=[("active", PANEL)], darkcolor=[("active", PANEL)], bordercolor=[("active", PANEL)])
    st.configure("TabOn.TButton", background=CARD, foreground=ACCENT, bordercolor=CARD, lightcolor=CARD,
                 darkcolor=CARD, padding=(px(18), px(8)), font=BOLD)
    st.map("TabOn.TButton", background=[("active", CARD)], lightcolor=[("active", CARD)],
           darkcolor=[("active", CARD)], bordercolor=[("active", CARD)])
    st.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
    st.configure("TNotebook.Tab", background=BG, foreground=MUTED, padding=(px(18), px(8)), borderwidth=0,
                 font=BOLD, lightcolor=BG, bordercolor=BG)
    st.map("TNotebook.Tab", background=[("selected", CARD), ("active", PANEL)],
           foreground=[("selected", ACCENT), ("active", TEXT)], lightcolor=[("selected", CARD)],
           bordercolor=[("selected", CARD)], expand=[("selected", (0, 0, 0, 0))])

    st.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, bordercolor=PANEL,
                 lightcolor=PANEL, darkcolor=PANEL, borderwidth=0, font=FONT)
    st.map("Treeview", background=[("selected", "focus", "#3b5590"), ("selected", SELECT)],
           foreground=[("selected", "#ffffff")])
    st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    st.configure("Vertical.TScrollbar", background=FIELD, troughcolor=PANEL, bordercolor=PANEL, arrowcolor=MUTED,
                 lightcolor=FIELD, darkcolor=FIELD, gripcount=0, arrowsize=px(12))
    st.map("Vertical.TScrollbar", background=[("active", FIELD_HI)], arrowcolor=[("active", ACCENT)])
    st.configure("Card.Vertical.TScrollbar", troughcolor=BG, bordercolor=BG)
    st.configure("TPanedwindow", background=BG)
    st.configure("Sash", sashthickness=px(5), background=BG, lightcolor=BG, bordercolor=BG)

    # Keyboard: the button that has the focus (Tab key) is drawn with an orange border; a mouse click does not give
    # the focus to a button (no orange border left behind after a click); Enter presses it, like Space.
    for name in ("TButton", "Accent.TButton", "Small.TButton", "Link.TButton", "Icon.TButton", "Char.TButton",
                 "Ghost.TButton", "Seg.TButton", "SegOn.TButton", "Tab.TButton", "TabOn.TButton"):
        st.map(name, relief=[("focus", "solid")],  # (a flat button has no border drawn)
               **{opt: [("focus", ACCENT)] + [tuple(s) for s in st.map(name, opt)]
                  for opt in ("bordercolor", "lightcolor", "darkcolor")})
    st.layout("TButton", [("Button.border", {"sticky": "nswe", "border": "1", "children": [
        ("Button.padding", {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})]})])  # (no dots)
    press = root.bind_class("TButton", "<ButtonPress-1>")
    if "ttk::clickToFocus %W;" in press:
        root.bind_class("TButton", "<ButtonPress-1>", press.replace("ttk::clickToFocus %W;", ""))
    root.bind_class("TButton", "<Return>", "%W instate !disabled {%W invoke}")
    # The mouse wheel scrolls the page, never changes the value of a list or a number box under the pointer.
    for cls in ("TCombobox", "TSpinbox"):
        for seq in ("<MouseWheel>", "<Shift-MouseWheel>"):
            root.unbind_class(cls, seq)
    return S


def dark_title(win, show=False):
    """A dark title bar for the window (Windows 10 2004 and later; nothing elsewhere). show: the window was kept
    fully transparent until now and appears."""
    try:
        import ctypes
        hwnd = int(win.wm_frame(), 16)
        on = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (19 before Windows 10 2004)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), ctypes.sizeof(on)) == 0:
                break
    except Exception:
        pass
    # Windows 10 draws the title bar again only after a change of the window: a change of its opacity is one that
    # does not move anything (a redraw request or "frame changed" is not enough).
    hidden = float(win.attributes("-alpha")) == 0.0
    if hidden and not show:
        return  # (a window kept invisible on purpose: the tests' screenshots)
    if not hidden:
        win.attributes("-alpha", 0.999)
    win.attributes("-alpha", 1.0)


# ---- small helpers ------------------------------------------------------------------------------------------------
def entry(parent, var, width=10, bg=CARD, **kw):
    """A text box of the theme (tk.Entry: its colour can show a changed or a wrong value)."""
    return tk.Entry(parent, textvariable=var, width=width, bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat",
                    highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT, font=FONT,
                    disabledbackground=PANEL, disabledforeground=MUTED, **kw)


def gradient(canvas, w, h, top, bottom, tag="bg", steps=56):
    canvas.delete(tag)
    a = [int(top[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(bottom[i:i + 2], 16) for i in (1, 3, 5)]
    for k in range(steps):
        t = k / (steps - 1)
        col = "#%02x%02x%02x" % tuple(int(a[c] + (b[c] - a[c]) * t) for c in range(3))
        y0, y1 = h * k // steps, h * (k + 1) // steps + 1
        canvas.create_rectangle(0, y0, w, y1, fill=col, width=0, tags=tag)
    canvas.tag_lower(tag)


class Tooltip:
    """A little box of text shown when the mouse rests on a widget."""

    def __init__(self, widget, text):
        self.widget, self.text, self.tip, self.job = widget, text, None, None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, _e):
        if self.text:
            self.job = self.widget.after(450, self._show)

    def _leave(self, _e=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None

    def _show(self):
        text = self.text() if callable(self.text) else self.text
        if not text:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.configure(bg=BORDER)
        tk.Label(self.tip, text=text, bg="#0d1017", fg=TEXT, font=SMALL, justify="left", padx=px(8), pady=px(5),
                 wraplength=pz(360)).pack(padx=1, pady=1)
        x = self.widget.winfo_rootx() + px(8)
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + px(4)
        self.tip.wm_geometry(f"+{x}+{y}")


class ScrollPage(ttk.Frame):
    """A page that scrolls; put the content in .inner. The window sends it the mouse wheel (scroll), and says when
    it is the page on screen (shown): a hidden page follows the window's width only when it is shown again (with
    five pages, resizing the window is five times quicker)."""

    def __init__(self, parent):
        super().__init__(parent, style="TFrame")
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=BG, bd=0, yscrollincrement=1)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview, style="Card.Vertical.TScrollbar")
        self.inner = ttk.Frame(self.canvas, style="TFrame", padding=(px(14), px(12), px(14), px(16)))
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=(0, 0, e.width, e.height)))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", self._resized)
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.shown, self.width, self.fitted = True, 0, 0
        self.wraps = []          # labels whose lines wrap at the page's width (hint, note)
        self.target, self.job = None, None

    # -- width
    def _resized(self, e):
        self.width = e.width
        if self.shown:
            self.fit()

    def fit(self, force=False):
        """The content takes the page's width; the texts wrap at it."""
        if not self.width or (self.width == self.fitted and not force):
            return
        self.fitted = self.width
        self.canvas.itemconfigure(self.win, width=self.width)
        for lab in self.wraps:
            rewrap(lab, self.width)

    # -- the mouse wheel: a smooth glide of a few pixels at a time to the place asked for
    def scroll(self, pixels):
        total = self.inner.winfo_height()
        view = self.canvas.winfo_height()
        if total <= view:
            return
        start = self.canvas.canvasy(0) if self.target is None else self.target
        self.target = max(0, min(total - view, start + pixels))
        if self.job is None:
            self._glide()

    def _glide(self):
        total = max(1, self.inner.winfo_height())
        now = self.canvas.canvasy(0)
        gap = self.target - now
        if abs(gap) < 2:
            self.canvas.yview_moveto(self.target / total)
            self.target = self.job = None
            return
        step = gap * 0.5 if abs(gap) > 6 else gap
        self.canvas.yview_moveto((now + step) / total)
        self.job = self.after(12, self._glide)

    def top(self):
        if self.job:
            self.after_cancel(self.job)
        self.target = self.job = None
        self.canvas.yview_moveto(0)

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.wraps = []
        self.top()


def page_of(widget):
    while widget is not None and not isinstance(widget, ScrollPage):
        widget = widget.master
    return widget


def rewrap(lab, page_width):
    """A text of a page wraps at its width (at most lab.wrap, which follows the text size); a note keeps the lines
    its longest text needs."""
    lab.wrapw = max(px(220), min(pz(lab.wrap), page_width - px(76)))
    lab.configure(wraplength=lab.wrapw)
    if getattr(lab, "lines", None):
        set_note(lab, lab.cget("text"), fit=True)


def set_note(lab, text, fit=False):
    """Text of a note: its height grows to what its text needs (never shrinks: the page under it does not move from
    one character to another)."""
    if not fit and text == lab.cget("text"):
        return
    if not fit:
        lab.configure(text=text)
    need = text_lines(lab.font, text, getattr(lab, "wrapw", pz(lab.wrap))) if text else 0
    if fit:
        lab.lines = max(lab.base_lines, need)
        lab.configure(height=lab.lines)
    elif need > lab.lines:
        lab.lines = need
        lab.configure(height=need)


def card(parent, title=None, subtitle=None, accent=False):
    """A block of the page: a dark rounded-looking box with a title; returns the frame to fill."""
    outer = tk.Frame(parent, bg=ACCENT if accent else BORDER)
    outer.pack(fill="x", pady=(0, px(12)))
    box = ttk.Frame(outer, style="Card.TFrame", padding=(px(16), px(12), px(16), px(14)))
    box.pack(fill="both", expand=True, padx=(px(3) if accent else 0, 0))
    body = ttk.Frame(box, style="Card.TFrame")
    if title:
        head = ttk.Frame(box, style="Card.TFrame")
        head.pack(fill="x", pady=(0, px(6)))
        body.title = ttk.Label(head, text=title, style="Card.Title.TLabel")
        body.title.pack(side="left")
        body.sub = ttk.Label(head, text=subtitle or "", style="Card.Muted.TLabel")
        body.sub.pack(side="left", padx=px(10), pady=(px(3), 0))
        body.head = head
    body.pack(fill="both", expand=True)
    return body


def _wrapping(lab, wrap):
    """The label wraps at its page's width (see rewrap)."""
    lab.wrap = wrap
    page = page_of(lab.master)
    if page is not None:
        page.wraps.append(lab)
        if page.fitted:
            rewrap(lab, page.fitted)
            return lab
    lab.wrapw = pz(wrap)
    lab.configure(wraplength=lab.wrapw)
    return lab


def hint(parent, text, wrap=760, pady=(0, 6)):
    """An explanation in a card (the size of the text of the values: easy to read)."""
    lab = ttk.Label(parent, text=text, style="Card.Hint.TLabel", justify="left")
    lab.pack(anchor="w", pady=(px(pady[0]), px(pady[1])))
    return _wrapping(lab, wrap)


def note(parent, lines, wrap=760):
    """An explanation whose text changes with the character (set_note): its height only grows, so a text that
    changes does not move the page around it."""
    lab = tk.Label(parent, text="", bg=CARD, fg=MUTED, font=FONT, justify="left", anchor="nw", height=lines)
    lab.font, lab.lines, lab.base_lines = FONT, lines, lines
    lab.pack(anchor="w", fill="x", pady=(0, px(6)))
    return _wrapping(lab, wrap)


def ball_png(size):
    """The tool's icon: an orange crystal ball with a red star (drawn here, nothing taken from the game); a PNG as
    base64 text, which tk.PhotoImage takes as data."""
    import base64
    import math
    import struct
    import zlib
    star = []
    for k in range(10):  # five points, one upward
        r = 0.40 if k % 2 == 0 else 0.17
        a = -math.pi / 2 + k * math.pi / 5
        star.append((r * math.cos(a) + 0.02, r * math.sin(a) + 0.04))

    def in_star(x, y):
        inside = False
        for i in range(10):
            (x1, y1), (x2, y2) = star[i], star[i - 1]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
        return inside

    n = 4 if size <= 64 else 2  # samples per pixel side
    rows = []
    for py in range(size):
        row = bytearray()
        for qx in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(n):
                for sx in range(n):
                    x = (qx + (sx + 0.5) / n) / size * 2 - 1
                    y = (py + (sy + 0.5) / n) / size * 2 - 1
                    d = x * x + y * y
                    if d > 0.96:
                        continue
                    if in_star(x, y):
                        col = (226, 38, 27)
                    else:
                        light = max(0.0, 1 - ((x + 0.38) ** 2 + (y + 0.42) ** 2) / 1.3)
                        edge = d / 0.96
                        col = (255, 150 + 90 * light - 60 * edge, 30 + 120 * light ** 3 - 20 * edge)
                        if (x + 0.42) ** 2 + (y + 0.46) ** 2 < 0.02:
                            col = (255, 246, 214)
                    acc[0] += col[0]
                    acc[1] += max(0, col[1])
                    acc[2] += max(0, col[2])
                    acc[3] += 1
            a = acc[3]
            row += bytes([int(acc[0] / a) if a else 0, int(acc[1] / a) if a else 0, int(acc[2] / a) if a else 0,
                          int(255 * a / (n * n))])
        rows.append(b"\0" + bytes(row))

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)) +
           chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


# ---- the character picker ------------------------------------------------------------------------------------------
class CharList(ttk.Frame):
    """A searchable list of characters with their chips (the side bar and the picker)."""

    def __init__(self, parent, names, icons, style_bg=PANEL, height=None, on_select=None, extra=None):
        super().__init__(parent, style="Panel.TFrame")
        self.names, self.icons, self.on_select, self.extra = names, icons, on_select, extra or (lambda c: "")
        self.tree = ttk.Treeview(self, show="tree", selectmode="browse", height=height or 10)
        self.tree.column("#0", width=px(280))
        bar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.tree.tag_configure("mod", foreground=ACCENT_HI)
        self.tree.tag_configure("rep", foreground="#9cc2ff")
        self.tree.tag_configure("none", foreground=MUTED)
        self.tree.bind("<<TreeviewSelect>>", self._select)
        self.visible = []

    def fill(self, ids, text_of, tags_of=lambda c: ()):
        self.tree.delete(*self.tree.get_children())
        self.visible = list(ids)
        for c in ids:
            kw = {"image": self.icons.get(c)} if self.icons.get(c) is not None else {}
            self.tree.insert("", "end", iid=str(c), text=text_of(c), tags=tags_of(c), **kw)

    def set_icons(self, icons):
        self.icons = icons
        for c in self.visible:
            if c >= 0 and icons.get(c) is not None:
                self.tree.item(str(c), image=icons[c])

    def select(self, c, see=True):
        if str(c) in self.tree.get_children():
            self.tree.selection_set(str(c))
            if see:
                self.tree.see(str(c))

    def selected(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _select(self, _e):
        c = self.selected()
        if c is not None and self.on_select:
            self.on_select(c)


class Picker(tk.Toplevel):
    """A window to choose a character: search, chips, double click. .result = id, NONE, or None (closed)."""
    NONE = -1
    HIDDEN = False  # (kept invisible by the tests' screenshots)

    def __init__(self, master, title, names, icons, allow_none=None, current=None, exclude=()):
        super().__init__(master)
        self.withdraw()
        self.title(title)
        self.configure(bg=PANEL)
        self.transient(master)
        self.result = None
        self.names = names
        self.exclude = set(exclude)
        top = ttk.Frame(self, style="Panel.TFrame", padding=(px(12), px(12), px(12), px(6)))
        top.pack(fill="x")
        ttk.Label(top, text=title, style="Panel.Title.TLabel").pack(anchor="w")
        self.q = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.q, style="Search.TEntry")
        e.pack(fill="x", pady=(px(8), 0))
        self.q.trace_add("write", lambda *a: self._filter())
        bot = ttk.Frame(self, style="Panel.TFrame", padding=(px(12), px(8), px(12), px(12)))
        bot.pack(fill="x", side="bottom")
        mid = ttk.Frame(self, style="Panel.TFrame", padding=(px(12), px(4)))
        mid.pack(fill="both", expand=True)
        self.list = CharList(mid, names, icons, height=6)
        self.list.pack(fill="both", expand=True)
        self.list.tree.bind("<Double-1>", lambda e: self._ok())
        self.list.tree.bind("<Return>", lambda e: self._ok())
        e.bind("<Return>", lambda e: self._ok())
        e.bind("<Down>", lambda e: (self.list.tree.focus_set(), self._first()))
        ttk.Button(bot, text="Choisir", style="Accent.TButton", command=self._ok).pack(side="right")
        ttk.Button(bot, text="Annuler", command=self.destroy).pack(side="right", padx=px(8))
        if allow_none:
            ttk.Button(bot, text=allow_none, command=self._none).pack(side="left")
        self._filter()
        if current is not None and current >= 0:
            self.list.select(current)
        self.bind("<Escape>", lambda e: self.destroy())
        w, h = pz(440), pz(580)
        x = master.winfo_rootx() + (master.winfo_width() - w) // 2
        y = master.winfo_rooty() + (master.winfo_height() - h) // 3
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        self.attributes("-alpha", 0.0)  # (visible with its dark title bar: see dark_title)
        self.deiconify()
        self.after(20, lambda: dark_title(self, show=not self.HIDDEN))
        self.grab_set()
        e.focus_set()

    def _filter(self):
        q = self.q.get().strip().lower()
        ids = [c for c in range(len(self.names)) if c not in self.exclude and
               (not q or q in self.names[c].lower() or q == str(c) or q == "%03d" % c)]
        self.list.fill(ids, lambda c: "  " + self.names[c])

    def _first(self):
        if self.list.visible and self.list.selected() is None:
            self.list.select(self.list.visible[0])

    def _ok(self):
        c = self.list.selected()
        if c is None and len(self.list.visible) == 1:
            c = self.list.visible[0]
        if c is not None:
            self.result = c
            self.destroy()

    def _none(self):
        self.result = self.NONE
        self.destroy()


class ShareDialog(tk.Toplevel):
    """Sharing a pack as a code: the pack's own code to copy, and a box to paste a friend's.
    load(text) loads a pasted code and returns None, or the message of what is wrong."""
    HIDDEN = False

    def __init__(self, master, code, mark, load):
        super().__init__(master)
        self.withdraw()
        self.title("Partager le pack")
        self.configure(bg=PANEL)
        self.transient(master)
        self.load = load
        pad = dict(padx=px(16))
        ttk.Label(self, text="Ton pack en code", style="Panel.Title.TLabel").pack(anchor="w", pady=(px(14), 0), **pad)
        ttk.Label(self, text="Copie ce code et colle-le dans un message (Discord…) : tes amis le chargent ici, "
                             "dans « Charger le pack d'un ami ».", style="Panel.Muted.TLabel", wraplength=pz(560),
                  justify="left").pack(anchor="w", **pad)
        self.code = tk.Text(self, height=5, wrap="char", bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat",
                            font=MONO, highlightthickness=1, highlightbackground=BORDER,
                            highlightcolor=ACCENT)
        self.code.insert("1.0", code)
        self.code.configure(state="disabled")
        self.code.pack(fill="x", pady=(px(8), px(6)), **pad)
        row = ttk.Frame(self, style="Panel.TFrame")
        row.pack(fill="x", **pad)
        self.copied = ttk.Label(row, text="", style="Good.Panel.TLabel")
        ttk.Button(row, text="Copier le code", style="Accent.TButton",
                   command=lambda: self._copy(code)).pack(side="left")
        self.copied.pack(side="left", padx=px(10))
        mk = ttk.Label(row, text=f"empreinte  {mark}", style="Panel.Accent.TLabel")
        mk.pack(side="right")
        Tooltip(mk, "L'empreinte résume ce que le pack change dans le jeu. Pour jouer en ligne ensemble, chaque "
                    "joueur doit avoir appliqué un pack de la même empreinte.")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=px(14), **pad)
        ttk.Label(self, text="Charger le pack d'un ami", style="Panel.Title.TLabel").pack(anchor="w", **pad)
        ttk.Label(self, text="Colle son code ci-dessous. Le pack ouvert ici sera remplacé par le sien.",
                  style="Panel.Muted.TLabel").pack(anchor="w", **pad)
        self.paste = tk.Text(self, height=5, wrap="char", bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat",
                             font=MONO, highlightthickness=1, highlightbackground=BORDER,
                             highlightcolor=ACCENT)
        self.paste.pack(fill="x", pady=(px(8), px(6)), **pad)
        row = ttk.Frame(self, style="Panel.TFrame")
        row.pack(fill="x", pady=(0, px(16)), **pad)
        ttk.Button(row, text="Charger ce pack", command=self._load).pack(side="left")
        ttk.Button(row, text="Fermer", command=self.destroy).pack(side="right")
        self.error = ttk.Label(self, text="", style="Warn.Panel.TLabel", wraplength=pz(560), justify="left")
        self.error.pack(anchor="w", pady=(0, px(12)), **pad)
        self.bind("<Escape>", lambda e: self.destroy())
        w = pz(600)
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - w) // 2
        y = master.winfo_rooty() + px(120)
        self.geometry(f"{w}x{self.winfo_reqheight()}+{max(0, x)}+{max(0, y)}")
        self.attributes("-alpha", 0.0)
        self.deiconify()
        self.after(20, lambda: dark_title(self, show=not self.HIDDEN))
        self.grab_set()
        self.paste.focus_set()

    def _copy(self, code):
        self.clipboard_clear()
        self.clipboard_append(code)
        self.copied.configure(text="✓ copié")

    def _load(self):
        problem = self.load(self.paste.get("1.0", "end"))
        if problem:
            self.error.configure(text=problem)
        else:
            self.destroy()


class InfoDialog(tk.Toplevel):
    """A small window with a table of two columns (the keyboard shortcuts)."""
    HIDDEN = False

    def __init__(self, master, title, rows):
        super().__init__(master)
        self.withdraw()
        self.title(title)
        self.configure(bg=PANEL)
        self.transient(master)
        box = ttk.Frame(self, style="Panel.TFrame", padding=(px(18), px(14), px(18), px(14)))
        box.pack(fill="both", expand=True)
        ttk.Label(box, text=title, style="Panel.Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w",
                                                                   pady=(0, px(10)))
        for i, (keys, what) in enumerate(rows, 1):
            ttk.Label(box, text=keys, style="Panel.Accent.TLabel").grid(row=i, column=0, sticky="w",
                                                                      padx=(0, px(18)), pady=px(3))
            ttk.Label(box, text=what, style="Panel.TLabel").grid(row=i, column=1, sticky="w", pady=px(3))
        close = ttk.Button(box, text="Fermer", command=self.destroy)
        close.grid(row=len(rows) + 1, column=1, sticky="e", pady=(px(14), 0))
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = master.winfo_rootx() + (master.winfo_width() - w) // 2
        y = master.winfo_rooty() + (master.winfo_height() - h) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.attributes("-alpha", 0.0)
        self.deiconify()
        self.after(20, lambda: dark_title(self, show=not self.HIDDEN))
        close.focus_set()


def pick(master, title, names, icons, **kw):
    p = Picker(master, title, names, icons, **kw)
    master.wait_window(p)
    return p.result
