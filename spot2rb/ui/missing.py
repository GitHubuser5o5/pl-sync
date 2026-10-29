from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog

from spot2rb.core.missing import label, missing_rows, missing_text, write_missing
from spot2rb.ui import dialogs as messagebox
from spot2rb.ui import theme
from spot2rb.ui.theme import Btn, DataTable, F


class MissingWindow(tk.Toplevel):
    """Songs with no downloaded file, with Save as TXT and Copy."""

    def __init__(self, app, playlist_name, rows):
        super().__init__(app)
        theme.init(self)
        self.app, self.playlist_name, self.rows = app, playlist_name, rows
        self.items = missing_rows(rows)
        self.title("Missing songs — " + playlist_name)
        self.geometry("720x560")
        self.minsize(520, 400)
        self.configure(bg=theme.PANEL)
        self.transient(app)
        theme.dark_titlebar(self)
        head = theme.frame(self, theme.PANEL)
        head.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(head, text="Missing songs", font=F.h2, bg=theme.PANEL, fg=theme.LABEL).pack(side="left")
        tk.Label(head, text=f"{len(self.items)} without a downloaded file", font=F.mono, bg=theme.PANEL, fg=theme.DIM).pack(side="right")
        theme.dim(self, "Songs from this playlist that have no file in your Rekordbox collection. Duplicates are not listed.",
                  font=F.small).pack(anchor="w", padx=20, pady=(0, 10))
        buttons = theme.frame(self, theme.PANEL)
        buttons.pack(side="bottom", fill="x", padx=20, pady=16)
        Btn(buttons, "Save as TXT…", self.save, variant="g").pack(side="right")
        Btn(buttons, "Copy", self.copy).pack(side="right", padx=8)
        Btn(buttons, "Close", self.destroy).pack(side="left")
        table = DataTable(self, [{"title": "Artist", "weight": 1}, {"title": "Title", "weight": 1.4}], row_height=30,
                          empty_text="Nothing is missing.")
        table.pack(fill="both", expand=True, padx=20)
        table.set_rows([(str(i), [", ".join(row["track"].get("artists", [])), row["track"]["title"]]) for i, row in enumerate(self.items)])
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()

    def save(self):
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", self.playlist_name).strip(". ") or "Playlist"
        folder = self.app.output_dir.get().strip()
        path = filedialog.asksaveasfilename(parent=self, initialfile=name + " - missing.txt", defaultextension=".txt",
                                            initialdir=folder if folder and Path(folder).is_dir() else None,
                                            filetypes=[("Text file", "*.txt")])
        if path:
            try:
                count = write_missing(path, self.rows)
            except OSError as error:
                messagebox.showerror("Could not save", str(error), parent=self)
                return
            messagebox.showinfo("Saved", f"{count} songs saved.\n\n{path}", parent=self)

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(missing_text(self.rows))
        self.app.status.set("Missing songs copied to the clipboard.")
