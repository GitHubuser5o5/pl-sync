"""CDJ-style dark theme: colors, fonts and the small custom Canvas controls the app is built from."""
import ctypes
import sys
import tkinter as tk
from tkinter import font as tkfont
from types import SimpleNamespace

# Surfaces
CHASSIS, PANEL, RAISED, WELL, HAIR = "#0B0C0E", "#14161A", "#1B1E23", "#0F1114", "#2A2E35"
# Text
LABEL, DIM, DISABLED = "#E8EAED", "#8B919A", "#5B616A"
# Lamps
GREEN, AMBER, BLUE, RED = "#34D17B", "#FF9F1C", "#2D9CFF", "#FF4D4F"
EMPTY = "#343B42"
# Rows
SEL, HOVER, ALT, ROWLINE = "#16304A", "#22262C", "#171A1E", "#20242A"
# Lit-pad tints
GREEN_HOVER, GREEN_PRESS, RED_HOVER, AMBER_HOVER = "#1D3A2B", "#0F2218", "#3A1C1E", "#3A2A10"

LAMP = {"g": GREEN, "a": AMBER, "r": RED}
# chip style -> (text color, border color)
CHIP = {"g": (GREEN, "#1D5A3A"), "a": (AMBER, "#6A4410"), "b": (BLUE, "#1A4A75"), "r": (RED, "#6E2526"),
        "n": (LABEL, HAIR), "d": (DIM, HAIR), "sk": (DIM, HAIR), "dp": (DIM, HAIR)}

F = SimpleNamespace()


def init(root):
    """Create the shared fonts once a Tk root exists (idempotent)."""
    if getattr(F, "ready", None) is root:
        return
    families = set(tkfont.families(root))
    default = tkfont.nametofont("TkDefaultFont", root=root).actual("family")
    fixed = tkfont.nametofont("TkFixedFont", root=root).actual("family")
    label = next((f for f in ("Bahnschrift", "Bahnschrift SemiCondensed", "Arial Narrow") if f in families), default)
    body = "Segoe UI" if "Segoe UI" in families else default
    mono = "Consolas" if "Consolas" in families else fixed
    F.label = tkfont.Font(root=root, family=label, size=10)
    F.zone = tkfont.Font(root=root, family=label, size=10)
    F.tab = tkfont.Font(root=root, family=label, size=11)
    F.title = tkfont.Font(root=root, family=label, size=21)
    F.tag = tkfont.Font(root=root, family=label, size=10)
    F.chip = tkfont.Font(root=root, family=label, size=9, weight="bold")
    F.body = tkfont.Font(root=root, family=body, size=10)
    F.bodyb = tkfont.Font(root=root, family=body, size=10, weight="bold")
    F.small = tkfont.Font(root=root, family=body, size=9)
    F.h2 = tkfont.Font(root=root, family=label, size=14)
    F.mono = tkfont.Font(root=root, family=mono, size=10)
    F.monosm = tkfont.Font(root=root, family=mono, size=9)
    F.symbol = tkfont.Font(root=root, family="Segoe UI Symbol" if "Segoe UI Symbol" in families else body, size=11)
    F.ready = root
    root.configure(bg=CHASSIS)
    root.option_add("*Font", F.body)


def dark_titlebar(win):
    """Ask Windows 10/11 for a dark native title bar (silently does nothing elsewhere)."""
    if sys.platform != "win32":
        return
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        value = ctypes.c_int(1)
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
        caption = ctypes.c_int(0x000E0C0B)  # COLORREF 0x00BBGGRR for #0B0C0E (Windows 11 only)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
    except Exception:
        pass


def frame(parent, bg=PANEL, **kw):
    return tk.Frame(parent, bg=bg, bd=0, highlightthickness=0, **kw)


def box(parent, bg=PANEL, border=HAIR, **kw):
    """A frame with a 1 px hairline border."""
    return tk.Frame(parent, bg=bg, bd=0, highlightthickness=1, highlightbackground=border, highlightcolor=border, **kw)


def label(parent, text="", color=LABEL, font=None, bg=None, **kw):
    return tk.Label(parent, text=text, fg=color, bg=bg or _bg(parent), font=font or F.body, bd=0, anchor="w", justify="left", **kw)


def dim(parent, text="", **kw):
    return label(parent, text, color=DIM, **kw)


def entry(parent, variable, **kw):
    """Dark readout well for text and paths."""
    return tk.Entry(parent, textvariable=variable, bg=RAISED, fg=LABEL, insertbackground=LABEL, disabledbackground=PANEL,
                    disabledforeground=DISABLED, readonlybackground=RAISED, selectbackground=SEL, selectforeground=LABEL,
                    relief="flat", bd=0, highlightthickness=1, highlightbackground=HAIR, highlightcolor=BLUE, font=F.mono, **kw)


def _bg(parent):
    try:
        return parent.cget("bg")
    except tk.TclError:
        return PANEL


def mix(a, b, t):
    """Blend two #rrggbb colors; t=0 gives a, t=1 gives b."""
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def spaced_width(font, text, spacing=0.08):
    if not text:
        return 0
    step = spacing * font.measure("M")
    return sum(font.measure(c) for c in text) + step * (len(text) - 1)


def draw_spaced(canvas, x, y, text, font, fill, spacing=0.08, anchor="w", tags=()):
    """Draw text one letter at a time to get tracking, which Tk cannot do natively. Returns the width."""
    step = spacing * font.measure("M")
    widths = [font.measure(c) for c in text]
    total = sum(widths) + step * max(0, len(text) - 1)
    if anchor == "center":
        x -= total / 2
    elif anchor == "e":
        x -= total
    start = x
    for char, width in zip(text, widths):
        if char != " ":
            canvas.create_text(x, y, text=char, font=font, fill=fill, anchor="w", tags=tags)
        x += width + step
    return total


def fit(text, font, width, middle=False):
    """Shorten text with an ellipsis so it fits `width` pixels."""
    if width <= 0:
        return ""
    if font.measure(text) <= width:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if middle:
            head = (mid + 1) // 2
            candidate = text[:head] + "…" + text[len(text) - (mid - head):] if mid - head else text[:head] + "…"
        else:
            candidate = text[:mid] + "…"
        if font.measure(candidate) <= width:
            low = mid
        else:
            high = mid - 1
    if middle:
        head = (low + 1) // 2
        tail = low - head
        return text[:head] + "…" + (text[len(text) - tail:] if tail else "")
    return text[:low] + "…"


class Btn(tk.Canvas):
    """Rubber-pad button. variant: '' secondary, 'g' green (PLAY), 'a' amber (CUE), 'r' red."""

    def __init__(self, parent, text="", command=None, variant="", small=False, minwidth=None, bg=None, **kw):
        self._text, self._command, self._variant, self._small = text, command, variant, small
        self._state, self._hover, self._press, self._focus = "normal", False, False, False
        self._minwidth = (0 if small else 96) if minwidth is None else minwidth
        self._h = 26 if small else 30
        super().__init__(parent, width=self._calc_width(), height=self._h, bg=bg or _bg(parent), bd=0, highlightthickness=0,
                         takefocus=1, cursor="hand2", **kw)
        for sequence, handler in (("<Enter>", self._enter), ("<Leave>", self._leave), ("<ButtonPress-1>", self._down),
                                  ("<ButtonRelease-1>", self._up), ("<FocusIn>", self._focus_in), ("<FocusOut>", self._focus_out),
                                  ("<space>", self._key), ("<Return>", self._key)):
            tk.Canvas.bind(self, sequence, handler)
        self._draw()

    def _calc_width(self):
        return max(self._minwidth, int(spaced_width(F.label, self._text.upper())) + 28)

    # -- tk-style configuration -------------------------------------------------
    def configure(self, cnf=None, **kw):
        cnf = dict(cnf or {}, **kw)
        changed = False
        if "text" in cnf:
            self._text = cnf.pop("text")
            cnf["width"] = self._calc_width()
            changed = True
        if "command" in cnf:
            self._command = cnf.pop("command")
        if "state" in cnf:
            self._state = "disabled" if str(cnf.pop("state")) == "disabled" else "normal"
            self.configure_cursor()
            changed = True
        if "variant" in cnf:
            self._variant = cnf.pop("variant")
            changed = True
        if cnf:
            super().configure(cnf)
        if changed:
            self._draw()

    config = configure

    def configure_cursor(self):
        super().configure(cursor="arrow" if self._state == "disabled" else "hand2")

    def cget(self, key):
        if key == "text":
            return self._text
        if key == "state":
            return self._state
        return super().cget(key)

    def invoke(self):
        if self._state != "disabled" and self._command:
            self._command()

    # -- events -------------------------------------------------------------------
    def _enter(self, _):
        self._hover = True
        self._draw()

    def _leave(self, _):
        self._hover = self._press = False
        self._draw()

    def _down(self, _):
        if self._state != "disabled":
            self._press = True
            self._draw()

    def _up(self, event):
        was = self._press
        self._press = False
        self._draw()
        if was and 0 <= event.x < int(self["width"]) and 0 <= event.y < self._h:
            self.invoke()

    def _focus_in(self, _):
        self._focus = True
        self._draw()

    def _focus_out(self, _):
        self._focus = False
        self._draw()

    def _key(self, _):
        self.invoke()
        return "break"

    def bind(self, sequence=None, func=None, add=None):
        return super().bind(sequence, func, add="+")

    # -- drawing --------------------------------------------------------------------
    def _draw(self):
        self.delete("all")
        w, h, v = int(self["width"]), self._h, self._variant
        lamp = LAMP.get(v)
        if self._state == "disabled":
            fill, border, lamp, color = PANEL, "#22252B", None, DISABLED
        else:
            fill, border, color = RAISED, lamp or HAIR, LABEL
            if self._press:
                fill, border = {"g": GREEN_PRESS, "r": RED_HOVER, "a": AMBER_HOVER}.get(v, CHASSIS), lamp or "#1F2328"
            elif self._hover:
                fill, border = {"g": GREEN_HOVER, "r": RED_HOVER, "a": AMBER_HOVER}.get(v, "#252930"), lamp or "#3A3F48"
        points = (1, 0, w - 2, 0, w - 1, 1, w - 1, h - 2, w - 2, h - 1, 1, h - 1, 0, h - 2, 0, 1)
        self.create_polygon(points, fill=fill, outline=border)
        if self._press and self._state != "disabled":
            self.create_rectangle(1, 1, w - 2, 2, fill="#000000", outline="#000000")
        if lamp:
            self.create_rectangle(1, h - 4, w - 2, h - 2, fill=lamp, outline=lamp)
        draw_spaced(self, w / 2, h / 2 - (1 if lamp else 0), self._text.upper(), F.label, color, anchor="center")
        if self._focus:
            self.create_rectangle(2, 2, w - 3, h - 3, outline=BLUE, width=2)


class Spinner(tk.Canvas):
    """Thin rotating ring: a 90 degree arc advancing 30 degrees every 70 ms."""

    def __init__(self, parent, size=14, color=AMBER, bg=None):
        super().__init__(parent, width=size, height=size, bg=bg or _bg(parent), bd=0, highlightthickness=0)
        self.size, self.color, self.angle, self.job = size, color, 0, None
        self._draw()

    def _draw(self):
        self.delete("all")
        width = 3 if self.size > 20 else 2
        pad = width / 2 + 0.5
        box_ = (pad, pad, self.size - pad, self.size - pad)
        self.create_oval(*box_, outline=EMPTY, width=width)
        self.create_arc(*box_, start=self.angle, extent=90, style="arc", outline=self.color, width=width)

    def start(self):
        if self.job is None:
            self._tick()

    def _tick(self):
        self.angle = (self.angle - 30) % 360
        self._draw()
        self.job = self.after(70, self._tick)

    def stop(self):
        if self.job is not None:
            self.after_cancel(self.job)
            self.job = None

    def destroy(self):
        self.stop()
        super().destroy()


class Check(tk.Canvas):
    """16 px checkbox with a label."""

    def __init__(self, parent, text, variable, command=None, bg=None):
        self.variable, self._command, self._text, self._state, self._focus = variable, command, text, "normal", False
        super().__init__(parent, width=26 + F.body.measure(text), height=22, bg=bg or _bg(parent), bd=0, highlightthickness=0,
                         takefocus=1, cursor="hand2")
        tk.Canvas.bind(self, "<ButtonRelease-1>", lambda e: self.toggle())
        tk.Canvas.bind(self, "<space>", lambda e: self.toggle())
        tk.Canvas.bind(self, "<FocusIn>", lambda e: self._set_focus(True))
        tk.Canvas.bind(self, "<FocusOut>", lambda e: self._set_focus(False))
        self.variable.trace_add("write", lambda *_: self._draw())
        self._draw()

    def _set_focus(self, value):
        self._focus = value
        self._draw()

    def toggle(self):
        if self._state == "disabled":
            return
        self.variable.set(not self.variable.get())
        if self._command:
            self._command()

    def _draw(self):
        self.delete("all")
        on = bool(self.variable.get())
        off = self._state == "disabled"
        self.create_rectangle(1, 3, 17, 19, fill=GREEN if on and not off else RAISED, outline=GREEN if on and not off else "#5B616A")
        if on:
            self.create_text(9, 11, text="✓", fill=CHASSIS, font=F.symbol)
        self.create_text(26, 11, text=self._text, fill=DISABLED if off else LABEL, font=F.body, anchor="w")
        if self._focus:
            self.create_rectangle(0, 2, 19, 20, outline=BLUE, width=1)


class Switch(tk.Canvas):
    """34 x 16 slide switch with a label (lit green when on)."""

    def __init__(self, parent, text, variable, command=None, bg=None):
        self.variable, self._command, self._text, self._focus = variable, command, text, False
        super().__init__(parent, width=44 + F.body.measure(text), height=22, bg=bg or _bg(parent), bd=0, highlightthickness=0,
                         takefocus=1, cursor="hand2")
        tk.Canvas.bind(self, "<ButtonRelease-1>", lambda e: self.toggle())
        tk.Canvas.bind(self, "<space>", lambda e: self.toggle())
        tk.Canvas.bind(self, "<FocusIn>", lambda e: self._set_focus(True))
        tk.Canvas.bind(self, "<FocusOut>", lambda e: self._set_focus(False))
        self.variable.trace_add("write", lambda *_: self._draw())
        self._draw()

    def _set_focus(self, value):
        self._focus = value
        self._draw()

    def toggle(self):
        self.variable.set(not self.variable.get())
        if self._command:
            self._command()

    def _draw(self):
        self.delete("all")
        on = bool(self.variable.get())
        self.create_rectangle(1, 3, 35, 19, fill=RAISED, outline=GREEN if on else "#5B616A")
        x = 21 if on else 4
        self.create_rectangle(x, 6, x + 10, 16, fill=GREEN if on else DIM, outline=GREEN if on else DIM)
        self.create_text(44, 11, text=self._text, fill=LABEL, font=F.body, anchor="w")
        if self._focus:
            self.create_rectangle(0, 2, 37, 20, outline=BLUE, width=1)


class Seek(tk.Canvas):
    """4 px track with a green fill and an 8 x 16 thumb (ttk.Scale-compatible: set, get, configure(to=))."""

    def __init__(self, parent, from_=0, to=1, bg=None):
        self._from, self._to, self._value, self._drag = from_, to, from_, False
        super().__init__(parent, height=20, bg=bg or _bg(parent), bd=0, highlightthickness=0, cursor="hand2")
        tk.Canvas.bind(self, "<Configure>", lambda e: self._draw())
        tk.Canvas.bind(self, "<ButtonPress-1>", self._press)
        tk.Canvas.bind(self, "<B1-Motion>", self._move)

    def bind(self, sequence=None, func=None, add=None):
        return super().bind(sequence, func, add="+")

    def configure(self, cnf=None, **kw):
        cnf = dict(cnf or {}, **kw)
        if "to" in cnf:
            self._to = cnf.pop("to")
        if "from_" in cnf:
            self._from = cnf.pop("from_")
        if cnf:
            super().configure(cnf)
        self._draw()

    config = configure

    def set(self, value):
        self._value = min(max(value, self._from), self._to)
        self._draw()

    def get(self):
        return self._value

    def _fraction(self):
        span = (self._to - self._from) or 1
        return (self._value - self._from) / span

    def _at(self, x):
        width = max(1, self.winfo_width() - 8)
        self._value = self._from + (self._to - self._from) * min(max((x - 4) / width, 0), 1)
        self._draw()

    def _press(self, event):
        self._at(event.x)

    def _move(self, event):
        self._at(event.x)

    def _draw(self):
        self.delete("all")
        width = self.winfo_width()
        if width < 20:
            return
        cy, x = 10, 4 + self._fraction() * (width - 8)
        self.create_rectangle(0, cy - 2, width, cy + 2, fill=EMPTY, outline=EMPTY)
        self.create_rectangle(0, cy - 2, x, cy + 2, fill=GREEN, outline=GREEN)
        self.create_rectangle(x - 4, cy - 8, x + 4, cy + 8, fill=LABEL, outline=LABEL)


class TabStrip(tk.Canvas):
    """CDJ mode-button tab row; the active tab is lit with a green bar along its top edge."""

    def __init__(self, parent, names, command, bg=CHASSIS):
        self.names, self.command, self.active, self.hover, self._focus = list(names), command, 0, None, False
        super().__init__(parent, height=34, bg=bg, bd=0, highlightthickness=0, takefocus=1, cursor="hand2")
        self.spans = []
        tk.Canvas.bind(self, "<Motion>", self._motion)
        tk.Canvas.bind(self, "<Leave>", lambda e: self._set_hover(None))
        tk.Canvas.bind(self, "<ButtonRelease-1>", self._click)
        tk.Canvas.bind(self, "<Left>", lambda e: self.select(max(0, self.active - 1)))
        tk.Canvas.bind(self, "<Right>", lambda e: self.select(min(len(self.names) - 1, self.active + 1)))
        tk.Canvas.bind(self, "<FocusIn>", lambda e: self._set_focus(True))
        tk.Canvas.bind(self, "<FocusOut>", lambda e: self._set_focus(False))
        self._draw()

    def _set_focus(self, value):
        self._focus = value
        self._draw()

    def _index_at(self, x):
        return next((i for i, (a, b) in enumerate(self.spans) if a <= x < b), None)

    def _motion(self, event):
        self._set_hover(self._index_at(event.x))

    def _set_hover(self, value):
        if value != self.hover:
            self.hover = value
            self._draw()

    def _click(self, event):
        index = self._index_at(event.x)
        if index is not None:
            self.select(index)

    def select(self, index):
        if index != self.active:
            self.active = index
            self._draw()
            self.command(index)

    def _draw(self):
        self.delete("all")
        x, self.spans = 0, []
        for index, name in enumerate(self.names):
            width = int(spaced_width(F.tab, name.upper(), 0.1)) + 44
            on, hover = index == self.active, index == self.hover
            fill = PANEL if on else (RAISED if hover else CHASSIS)
            self.create_rectangle(x, 0, x + width, 34, fill=fill, outline=HAIR)
            if on:
                self.create_rectangle(x + 1, 1, x + width - 1, 3, fill=GREEN, outline=GREEN)
                self.create_rectangle(x + 1, 33, x + width - 1, 34, fill=PANEL, outline=PANEL)
            draw_spaced(self, x + width / 2, 18, name.upper(), F.tab, LABEL if on or hover else DIM, 0.1, "center")
            if on and self._focus:
                self.create_rectangle(x + 4, 6, x + width - 4, 30, outline=BLUE, width=2)
            self.spans.append((x, x + width))
            x += width + 2


class VBar(tk.Canvas):
    """10 px scrollbar: dark track, grey thumb. Works with any yview-style owner via `command`."""

    def __init__(self, parent, command):
        super().__init__(parent, width=10, bg=WELL, bd=0, highlightthickness=0)
        self.command, self.first, self.last, self.hover, self.grab = command, 0.0, 1.0, False, None
        tk.Canvas.bind(self, "<Configure>", lambda e: self._draw())
        tk.Canvas.bind(self, "<Enter>", lambda e: self._set_hover(True))
        tk.Canvas.bind(self, "<Leave>", lambda e: self._set_hover(False))
        tk.Canvas.bind(self, "<ButtonPress-1>", self._press)
        tk.Canvas.bind(self, "<B1-Motion>", self._drag)

    def _set_hover(self, value):
        self.hover = value
        self._draw()

    def set(self, first, last):
        self.first, self.last = float(first), float(last)
        self._draw()

    def _draw(self):
        self.delete("all")
        height = self.winfo_height()
        if self.last - self.first >= 0.999 or height < 20:
            return
        self.create_rectangle(1, self.first * height, 9, max(self.last * height, self.first * height + 18),
                              fill=DISABLED if self.hover else EMPTY, outline="")

    def _press(self, event):
        height = max(1, self.winfo_height())
        fraction = event.y / height
        if self.first <= fraction <= self.last:
            self.grab = fraction - self.first
        else:
            self.grab = (self.last - self.first) / 2
            self.command("moveto", fraction - self.grab)

    def _drag(self, event):
        if self.grab is not None:
            self.command("moveto", event.y / max(1, self.winfo_height()) - self.grab)


class ScrollFrame(tk.Frame):
    """A vertically scrolling panel; put widgets in `.inner`."""

    def __init__(self, parent, bg=PANEL):
        super().__init__(parent, bg=bg, bd=0, highlightthickness=0)
        self.canvas = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        self.bar = VBar(self, lambda *a: self.canvas.yview(*a))
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y")
        self.inner = tk.Frame(self.canvas, bg=bg, bd=0, highlightthickness=0)
        self.window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self._sync())
        self.canvas.bind("<Configure>", lambda e: self._sync())
        for widget in (self.canvas, self.inner):
            widget.bind("<MouseWheel>", self._wheel)

    def _sync(self):
        self.canvas.itemconfigure(self.window, width=self.canvas.winfo_width())
        self.canvas.configure(scrollregion=(0, 0, 0, self.inner.winfo_reqheight()))
        if self.inner.winfo_reqheight() <= self.canvas.winfo_height():
            self.canvas.yview_moveto(0)

    def _wheel(self, event):
        if self.inner.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")


class DataTable(tk.Frame):
    """Dark list/table drawn on a Canvas: header row, hover/alt/selected rows, chips and the confidence meter.

    Columns: dict(title, width=px or weight=flex share, kind). Kinds: text, dim, mono, monodim, chip, meter, check.
    A cell is a plain string (drawn per its column kind) or a tuple:
    ("chip", style, text[, spinning]) · ("meter", level 0-5) · ("check", bool) · ("dim"|"mono"|"monodim"|"text", string).
    """

    GAP, PAD = 12, 10

    def __init__(self, parent, columns, mode="browse", row_height=30, header=True, empty_text="", bg=WELL):
        super().__init__(parent, bg=bg, bd=0, highlightthickness=1, highlightbackground=HAIR, highlightcolor=BLUE)
        self.columns, self.mode, self.rh, self.empty_text = columns, mode, row_height, empty_text
        self.rows, self.keys, self.sel, self.anchor, self.hover, self.offset, self.spin = [], {}, [], None, None, 0, 0
        self.spin_job = None
        self.select_callbacks = []
        self.head = tk.Canvas(self, height=28 if header else 0, bg=PANEL, bd=0, highlightthickness=0)
        self.body = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0, takefocus=1)
        self.bar = VBar(self, self._bar_command)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        if header:
            self.head.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.bar.grid(row=1, column=1, sticky="ns")
        self.body.bind("<Configure>", lambda e: self._layout())
        self.body.bind("<ButtonPress-1>", self._click)
        self.body.bind("<Motion>", self._motion)
        self.body.bind("<Leave>", lambda e: self._set_hover(None))
        self.body.bind("<MouseWheel>", lambda e: self._scroll(-3 if e.delta > 0 else 3))
        self.body.bind("<Button-4>", lambda e: self._scroll(-3))
        self.body.bind("<Button-5>", lambda e: self._scroll(3))
        self.body.bind("<Up>", lambda e: self._step(-1))
        self.body.bind("<Down>", lambda e: self._step(1))
        self.body.bind("<Prior>", lambda e: self._step(-8))
        self.body.bind("<Next>", lambda e: self._step(8))
        self.body.bind("<Home>", lambda e: self._step(-10 ** 9))
        self.body.bind("<End>", lambda e: self._step(10 ** 9))
        self.body.bind("<space>", self._space)
        self.body.bind("<Control-a>", self._select_all)

    # -- data -----------------------------------------------------------------------
    def clear(self):
        self.rows, self.keys, self.sel, self.anchor, self.offset = [], {}, [], None, 0
        self._redraw()

    def add(self, iid, cells):
        self.keys[iid] = len(self.rows)
        self.rows.append((iid, list(cells)))
        self._redraw()
        return iid

    def set_rows(self, rows):
        """Replace everything at once: rows = [(iid, cells), ...]."""
        keep = [s for s in self.sel]
        self.rows = [(iid, list(cells)) for iid, cells in rows]
        self.keys = {iid: i for i, (iid, _) in enumerate(self.rows)}
        self.sel = [s for s in keep if s in self.keys]
        self.offset = min(self.offset, self._max_offset())
        self._redraw()

    def set_cells(self, iid, cells):
        self.rows[self.keys[iid]] = (iid, list(cells))
        self._redraw()

    def iids(self):
        return tuple(iid for iid, _ in self.rows)

    def exists(self, iid):
        return iid in self.keys

    def index(self, iid):
        return self.keys[iid]

    def selection(self):
        return tuple(self.sel)

    def selected_indexes(self):
        return sorted(self.keys[s] for s in self.sel)

    def select(self, iids, notify=True):
        if isinstance(iids, str):
            iids = [iids]
        iids = [i for i in iids if i in self.keys]
        if iids == self.sel:
            return
        self.sel = list(iids)
        if iids:
            self.anchor = iids[-1]
            self.see(iids[-1], redraw=False)
        self._redraw()
        if notify:
            for callback in list(self.select_callbacks):
                callback(None)

    def see(self, iid, redraw=True):
        if iid not in self.keys:
            return
        top = self.keys[iid] * self.rh
        height = max(self.body.winfo_height(), self.rh)
        if top < self.offset:
            self.offset = top
        elif top + self.rh > self.offset + height:
            self.offset = top + self.rh - height
        self.offset = max(0, min(self.offset, self._max_offset()))
        if redraw:
            self._redraw()

    def bind(self, sequence=None, func=None, add=None):
        if sequence == "<<TreeviewSelect>>":  # delivered directly so it also works before the window is mapped
            self.select_callbacks.append(func)
            return None
        return self.body.bind(sequence, func, add="+" if add is None else add)

    def focus_set(self):
        self.body.focus_set()

    # -- layout ---------------------------------------------------------------------
    def _layout(self):
        self.offset = max(0, min(self.offset, self._max_offset()))
        self._redraw()

    def _max_offset(self):
        return max(0, len(self.rows) * self.rh - self.body.winfo_height())

    def _widths(self):
        total = max(self.body.winfo_width(), 200)
        fixed = sum(c.get("width", 0) for c in self.columns)
        flex = [c for c in self.columns if "width" not in c]
        free = max(0, total - fixed - self.GAP * (len(self.columns) - 1) - 2 * self.PAD)
        weights = sum(c.get("weight", 1) for c in flex) or 1
        return [c["width"] if "width" in c else max(60, free * c.get("weight", 1) / weights) for c in self.columns]

    def _bar_command(self, action, fraction=0, *_):
        if action == "moveto":
            self.offset = max(0, min(float(fraction) * len(self.rows) * self.rh, self._max_offset()))
            self._redraw()

    # -- drawing --------------------------------------------------------------------
    def _redraw(self):
        if not self.winfo_exists():
            return
        body, width, height = self.body, self.body.winfo_width(), self.body.winfo_height()
        body.delete("all")
        widths = self._widths()
        xs, x = [], self.PAD
        for w in widths:
            xs.append(x)
            x += w + self.GAP
        self._draw_head(xs, widths)
        total = len(self.rows) * self.rh
        self.bar.set(self.offset / total if total else 0, min(1, (self.offset + height) / total) if total else 1)
        if not self.rows and self.empty_text:
            body.create_text(width / 2, min(height / 2, 80), text=self.empty_text, fill=DIM, font=F.body)
        first = int(self.offset // self.rh)
        last = min(len(self.rows), first + height // self.rh + 2)
        spinning = False
        for index in range(first, last):
            iid, cells = self.rows[index]
            top = index * self.rh - self.offset
            selected = iid in self.sel
            fill = SEL if selected else HOVER if index == self.hover else ALT if index % 2 else self.cget("bg")
            body.create_rectangle(0, top, width, top + self.rh, fill=fill, outline="")
            body.create_line(0, top + self.rh - 1, width, top + self.rh - 1, fill=ROWLINE)
            if selected:
                body.create_rectangle(1, top, width - 2, top + self.rh - 1, outline=BLUE)
            cy = top + self.rh / 2
            for column, cell, cx, cw in zip(self.columns, cells, xs, widths):
                spinning |= self._cell(column, cell, cx, cy, cw)
        self._set_spin(spinning)

    def _draw_head(self, xs, widths):
        head = self.head
        if int(head["height"]) == 0:
            return
        head.delete("all")
        head.create_rectangle(0, 0, 5000, 28, fill=PANEL, outline="")
        head.create_line(0, 27, 5000, 27, fill=HAIR)
        for column, x, w in zip(self.columns, xs, widths):
            draw_spaced(head, x, 14, fit(column.get("title", "").upper(), F.label, w), F.label, DIM, 0.08)

    def _cell(self, column, cell, x, cy, width):
        kind, value = column.get("kind", "text"), cell
        if isinstance(cell, tuple):
            kind, value = cell[0], cell[1:]
        body = self.body
        if kind == "meter":
            level = int(value[0] if isinstance(value, tuple) else value)
            body.create_rectangle(x, cy - 12, x + 58, cy + 12, fill="#07080A", outline=HAIR)
            for i in range(5):
                color = EMPTY
                if 1 <= level <= 3 and i < level:
                    color = AMBER
                    if level == 3 and i == 2:
                        color = "#B6B535"
                elif level >= 4 and i < level:
                    color = GREEN
                body.create_rectangle(x + 4 + i * 11, cy - 8, x + 4 + i * 11 + 9, cy + 9, fill=color, outline="")
            return False
        if kind == "chip":
            if not isinstance(cell, tuple):
                if not cell:
                    return False
                value = ("n", cell)
            style, text = value[0], value[1]
            spin = len(value) > 2 and value[2]
            color, border = CHIP.get(style, CHIP["n"])
            label_text = fit(str(text).upper(), F.chip, max(20, width - 28))
            inner = spaced_width(F.chip, label_text)
            chip_w = int(8 + 6 + 6 + inner + 8)
            body.create_rectangle(x, cy - 10, x + chip_w, cy + 10, fill=PANEL, outline=border)
            if spin:
                self.spin = (self.spin - 30) % 360
                body.create_arc(x + 8, cy - 5, x + 18, cy + 5, start=self.spin, extent=90, style="arc", outline=color, width=2)
            elif style == "sk":
                body.create_rectangle(x + 8, cy - 1, x + 16, cy + 1, fill=color, outline="")
            elif style == "dp":
                body.create_rectangle(x + 8, cy - 3, x + 14, cy + 3, outline=color)
            else:
                body.create_rectangle(x + 8, cy - 3, x + 14, cy + 3, fill=color, outline=color)
            draw_spaced(body, x + 8 + 6 + 6, cy, label_text, F.chip, color, 0.08)
            return bool(spin)
        if kind == "check":
            on = bool(value[0] if isinstance(value, tuple) else value)
            body.create_rectangle(x, cy - 8, x + 16, cy + 8, fill=GREEN if on else RAISED, outline=GREEN if on else DISABLED)
            if on:
                body.create_text(x + 8, cy, text="✓", fill=CHASSIS, font=F.symbol)
            return False
        text = value[0] if isinstance(value, tuple) else value
        font = F.mono if kind in ("mono", "monodim") else F.body
        color = DIM if kind in ("dim", "monodim") else LABEL
        body.create_text(x, cy, text=fit(str(text), font, width, middle=font is F.mono), font=font, fill=color, anchor="w")
        return False

    def _set_spin(self, spinning):
        if spinning and self.spin_job is None:
            self.spin_job = self.after(70, self._spin_tick)
        elif not spinning and self.spin_job is not None:
            self.after_cancel(self.spin_job)
            self.spin_job = None

    def _spin_tick(self):
        self.spin_job = None
        self._redraw()

    def destroy(self):
        if self.spin_job is not None:
            self.after_cancel(self.spin_job)
            self.spin_job = None
        super().destroy()

    # -- interaction ----------------------------------------------------------------
    def _row_at(self, y):
        index = int((y + self.offset) // self.rh)
        return index if 0 <= index < len(self.rows) else None

    def _motion(self, event):
        self._set_hover(self._row_at(event.y))

    def _set_hover(self, index):
        if index != self.hover:
            self.hover = index
            self._redraw()

    def _scroll(self, rows):
        self.offset = max(0, min(self.offset + rows * self.rh, self._max_offset()))
        self._redraw()

    def _click(self, event):
        self.body.focus_set()
        index = self._row_at(event.y)
        if index is None:
            return
        iid = self.rows[index][0]
        if self.mode == "multiple":
            self.select([s for s in self.sel if s != iid] if iid in self.sel else self.sel + [iid])
        elif self.mode == "extended" and event.state & 0x4:
            self.select([s for s in self.sel if s != iid] if iid in self.sel else self.sel + [iid])
        elif self.mode == "extended" and event.state & 0x1 and self.anchor in self.keys:
            a, b = sorted((self.keys[self.anchor], index))
            anchor = self.anchor
            self.select([self.rows[i][0] for i in range(a, b + 1)])
            self.anchor = anchor
        else:
            self.select([iid])

    def _step(self, delta):
        if not self.rows:
            return "break"
        current = self.keys[self.sel[-1]] if self.sel else (-1 if delta > 0 else len(self.rows))
        target = max(0, min(len(self.rows) - 1, current + delta))
        self.select([self.rows[target][0]])
        return "break"

    def _space(self, _):
        if self.mode == "multiple" and self.sel:
            return "break"
        return None

    def _select_all(self, _):
        if self.mode in ("extended", "multiple"):
            self.select([iid for iid, _ in self.rows])
        return "break"


class Zone(tk.Frame):
    """A labelled panel zone: hairline border, spaced uppercase title with a rule running to the edge."""

    def __init__(self, parent, title):
        super().__init__(parent, bg=PANEL, bd=0, highlightthickness=1, highlightbackground=HAIR)
        self.title = tk.Canvas(self, height=18, bg=PANEL, bd=0, highlightthickness=0)
        self.title.pack(fill="x", padx=16, pady=(14, 0))
        self.body = frame(self, PANEL)
        self.body.pack(fill="both", expand=True, padx=16, pady=(10, 16))
        self._text = title
        self.title.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        self.title.delete("all")
        used = draw_spaced(self.title, 0, 9, self._text.upper(), F.zone, LABEL, 0.12)
        self.title.create_line(used + 8, 9, max(used + 9, self.title.winfo_width()), 9, fill=HAIR)


class StatusBar(tk.Frame):
    """Full-width readout strip: lamp square (green done / amber warn / red error / grey idle) or a spinner while busy."""

    LEVELS = {"ok": GREEN, "warn": AMBER, "error": RED, "idle": DIM}

    def __init__(self, parent, variable):
        super().__init__(parent, bg=CHASSIS, bd=0, highlightthickness=0, height=44)
        tk.Frame(self, bg=HAIR, height=1).pack(fill="x", side="top")
        row = frame(self, CHASSIS)
        row.pack(fill="both", expand=True, padx=20)
        self.slot = frame(row, CHASSIS, width=16, height=16)
        self.slot.pack(side="left", pady=12)
        self.slot.pack_propagate(False)
        self.lamp = tk.Frame(self.slot, bg=DIM, width=8, height=8)
        self.lamp.place(relx=.5, rely=.5, anchor="center")
        self.spinner = Spinner(self.slot, 14, AMBER, CHASSIS)
        self.text = tk.Label(row, textvariable=variable, bg=CHASSIS, fg=LABEL, font=F.body, anchor="w", justify="left")
        self.text.pack(side="left", fill="x", expand=True, padx=(12, 0), pady=10)
        row.bind("<Configure>", lambda e: self.text.configure(wraplength=max(200, e.width - 60)))
        self.level = "idle"
        self.pack_propagate(True)

    def set_level(self, level):
        self.level = level
        self.lamp.configure(bg=self.LEVELS.get(level, DIM))

    def set_busy(self, busy):
        if busy:
            self.lamp.place_forget()
            self.spinner.place(relx=.5, rely=.5, anchor="center")
            self.spinner.start()
        else:
            self.spinner.stop()
            self.spinner.place_forget()
            self.lamp.place(relx=.5, rely=.5, anchor="center")


class Cap(tk.Canvas):
    """Small uppercase, letter-spaced caption (field names, zone sub-labels)."""

    def __init__(self, parent, text, color=DIM, font=None, spacing=0.08, bg=None):
        font = font or F.label
        super().__init__(parent, width=int(spaced_width(font, text.upper(), spacing)) + 2, height=font.metrics("linespace") + 4,
                         bg=bg or _bg(parent), bd=0, highlightthickness=0)
        self.create_rectangle(0, 0, 0, 0)
        draw_spaced(self, 0, int(self["height"]) / 2, text.upper(), font, color, spacing)


class BusyOverlay(tk.Toplevel):
    """Dims a window and shows a big hollow green spinner; the dimmed window cannot be clicked until close()."""

    def __init__(self, target, text=""):
        super().__init__(target)
        target = target.winfo_toplevel()
        self.target, self.angle, self.job = target, 0, None
        self.overrideredirect(True)
        self.configure(bg="#000000")
        try:
            self.attributes("-alpha", 0.65)
        except tk.TclError:
            pass
        target.update_idletasks()
        w, h = target.winfo_width(), target.winfo_height()
        self.geometry(f"{w}x{h}+{target.winfo_rootx()}+{target.winfo_rooty()}")
        self.canvas = tk.Canvas(self, bg="#000000", bd=0, highlightthickness=0, cursor="watch")
        self.canvas.pack(fill="both", expand=True)
        self.text = text
        self.canvas.bind("<Configure>", lambda e: self._draw())
        for sequence in ("<Key>", "<ButtonPress>"):
            self.canvas.bind(sequence, lambda e: "break")
        self.transient(target)
        self.lift()
        self.update_idletasks()
        try:
            self.grab_set()
            self.canvas.focus_set()
        except tk.TclError:
            pass
        self._tick()

    def _draw(self):
        c = self.canvas
        c.delete("all")
        cx, cy, r = c.winfo_width() / 2, c.winfo_height() / 2 - 12, 56
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#1D3A2B", width=8)
        c.create_arc(cx - r, cy - r, cx + r, cy + r, start=self.angle, extent=100, style="arc", outline=GREEN, width=8)
        if self.text:
            c.create_text(cx, cy + r + 34, text=self.text, fill=LABEL, font=F.body)

    def _tick(self):
        self.angle = (self.angle - 18) % 360
        self._draw()
        self.job = self.after(40, self._tick)

    def close(self):
        if self.job:
            self.after_cancel(self.job)
            self.job = None
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        self.target.focus_force()


def tooltip(widget, text, delay=350):
    """Small dark hover hint under a widget."""
    state = {"job": None, "tip": None}

    def hide(_=None):
        if state["job"]:
            widget.after_cancel(state["job"])
            state["job"] = None
        if state["tip"]:
            state["tip"].destroy()
            state["tip"] = None

    def show():
        state["job"] = None
        tip = tk.Toplevel(widget)
        tip.overrideredirect(True)
        tip.configure(bg=HAIR)
        tk.Label(tip, text=text, bg=RAISED, fg=LABEL, font=F.small, justify="left", wraplength=320, padx=10, pady=6, bd=0).pack(padx=1, pady=1)
        tip.update_idletasks()
        x = widget.winfo_rootx() + max(0, (widget.winfo_width() - tip.winfo_reqwidth()) // 2)
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        screen_w = widget.winfo_screenwidth()
        x = max(4, min(x, screen_w - tip.winfo_reqwidth() - 4))
        tip.geometry(f"+{x}+{y}")
        state["tip"] = tip

    def enter(_):
        hide()
        state["job"] = widget.after(delay, show)

    for sequence, handler in (("<Enter>", enter), ("<Leave>", hide), ("<ButtonPress>", hide), ("<Destroy>", hide)):
        tk.Canvas.bind(widget, sequence, handler, add="+")
