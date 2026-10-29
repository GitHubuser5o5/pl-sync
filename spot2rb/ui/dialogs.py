"""Dark in-app message boxes with the same call shapes as tkinter.messagebox."""
import tkinter as tk

from spot2rb.ui import theme
from spot2rb.ui.theme import Btn, F


ICONS = {"info": ("i", theme.BLUE), "warn": ("!", theme.AMBER), "error": ("✕", theme.RED),
         "ask": ("?", theme.BLUE), "danger": ("?", theme.RED), "ok": ("✓", theme.GREEN)}


class MessageBox(tk.Toplevel):
    def __init__(self, parent, title, message, kind="info", buttons=("OK",), default=0, danger_index=None, tips=None):
        super().__init__(parent)
        theme.init(self)
        self.result = None
        self.title(title)
        self.configure(bg=theme.PANEL)
        self.resizable(False, False)
        if parent is not None:
            self.transient(parent.winfo_toplevel())
        head, _, detail = message.partition("\n\n")
        body = theme.frame(self, theme.PANEL)
        body.pack(fill="both", expand=True, padx=20, pady=(18, 12))
        glyph, color = ICONS.get(kind, ICONS["info"])
        icon = tk.Canvas(body, width=28, height=28, bg=theme.PANEL, bd=0, highlightthickness=0)
        icon.create_rectangle(0, 0, 27, 27, fill=theme.PANEL, outline=theme.CHIP.get({theme.BLUE: "b", theme.AMBER: "a", theme.RED: "r", theme.GREEN: "g"}[color])[1])
        icon.create_text(14, 14, text=glyph, fill=color, font=F.bodyb)
        icon.pack(side="left", anchor="n")
        text = theme.frame(body, theme.PANEL)
        text.pack(side="left", fill="x", expand=True, padx=(14, 0))
        tk.Label(text, text=head, bg=theme.PANEL, fg=theme.LABEL, font=F.body, wraplength=360, justify="left", anchor="w").pack(anchor="w")
        if detail.strip():
            well = tk.Label(text, text=detail.strip(), bg=theme.WELL, fg=theme.DIM, font=F.monosm, wraplength=340, justify="left",
                            anchor="w", padx=10, pady=8, highlightthickness=1, highlightbackground=theme.HAIR)
            well.pack(anchor="w", fill="x", pady=(8, 0))
        row = theme.frame(self, theme.PANEL)
        row.pack(fill="x", padx=20, pady=(0, 16))
        self.buttons = []
        for index in reversed(range(len(buttons))):
            variant = "r" if index == danger_index else ("g" if index == default else "")
            button = Btn(row, buttons[index], command=lambda i=index: self.finish(i), variant=variant, minwidth=80)
            button.pack(side="right", padx=(8, 0))
            if tips and tips[index]:
                theme.tooltip(button, tips[index])
            self.buttons.append(button)
        self.buttons.reverse()
        self.bind("<Return>", lambda e: self.finish(default))
        self.bind("<Escape>", lambda e: self.finish(0))
        self.protocol("WM_DELETE_WINDOW", lambda: self.finish(0))
        self.update_idletasks()
        anchor = (parent.winfo_toplevel() if parent is not None else self)
        x = anchor.winfo_rootx() + max(0, (anchor.winfo_width() - self.winfo_reqwidth()) // 2)
        y = anchor.winfo_rooty() + max(0, (anchor.winfo_height() - self.winfo_reqheight()) // 3)
        self.geometry(f"+{x}+{y}")
        theme.dark_titlebar(self)
        self.grab_set()
        self.buttons[default].focus_set()

    def finish(self, index):
        self.result = index
        self.grab_release()
        self.destroy()


def _run(parent, title, message, kind, buttons, default=0, danger_index=None, tips=None):
    parent = parent or tk._default_root
    box = MessageBox(parent, title, message, kind, buttons, default, danger_index, tips)
    box.wait_window()
    return box.result


def showinfo(title, message, parent=None, icon="info", **_):
    _run(parent, title, message, icon, ("OK",))


def showwarning(title, message, parent=None, **_):
    _run(parent, title, message, "warn", ("OK",))


def showerror(title, message, parent=None, **_):
    _run(parent, title, message, "error", ("OK",))


def askyesno(title, message, parent=None, danger=False, **_):
    result = _run(parent, title, message, "danger" if danger else "ask", ("No", "Yes"), 1, 1 if danger else None)
    return result == 1


def ask_choice(title, message, buttons, default=0, parent=None, tips=None):
    """Show a popup with custom buttons; returns the index of the pressed one (Escape/close = 0)."""
    return _run(parent, title, message, "ask", tuple(buttons), default, tips=tips)
