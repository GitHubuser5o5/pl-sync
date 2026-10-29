from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog

from spot2rb.core.matcher import candidates, match_rekordbox, path_key
from spot2rb.core.m3u import write_playlist
from spot2rb.core.review import build_rows, needs_attention, confidence
from spot2rb.ui import dialogs as messagebox
from spot2rb.ui import theme
from spot2rb.ui.preview import Preview
from spot2rb.ui.theme import Btn, DataTable, F

STATUS_CHIPS = {"matched": ("g", "Matched"), "suggested": ("a", "Suggested"), "chosen": ("b", "Chosen"),
                "skipped": ("sk", "Skipped"), "duplicate": ("dp", "Duplicate"), "unmatched": ("r", "Unmatched")}


def status_chip(status):
    style, text = STATUS_CHIPS.get(status, ("a", "Not imported") if status.startswith("File found") else ("d", status[:16]))
    return ("chip", style, text)


class ExportWindow(tk.Toplevel):
    def __init__(self, app, playlist, attention_only=False, on_ready=None, rows=None, files=None):
        super().__init__(app)
        theme.init(self)
        self.app, self.playlist = app, playlist
        self.on_ready = on_ready
        self.title("Needs attention — " + playlist["name"])
        self.geometry("1100x750")
        self.minsize(860, 600)
        self.configure(bg=theme.PANEL)
        self.rows = rows if rows is not None else build_rows(playlist, app.library, app.collection, app.answers)
        files = files if files is not None else candidates(app.library, app.collection)
        self.allowed_paths = {path_key(item["path"]) for item in files if item.get("in_rekordbox")}

        head = theme.frame(self, theme.PANEL)
        head.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(head, text="Needs attention", font=F.h2, bg=theme.PANEL, fg=theme.LABEL).pack(side="left")
        tk.Label(head, text=playlist["name"], font=F.body, bg=theme.PANEL, fg=theme.DIM).pack(side="left", padx=(14, 0), pady=(3, 0))
        theme.dim(self, "Only files in your loaded Rekordbox XML are selected. Folder-only files are reported and excluded.").pack(anchor="w", padx=20, pady=(6, 0))
        self.summary = tk.Label(self, bg=theme.PANEL, fg=theme.LABEL, font=F.mono, anchor="w", justify="left")
        self.summary.pack(anchor="w", padx=20, pady=(8, 0))
        self.notice = tk.Label(self, bg=theme.PANEL, fg=theme.AMBER, font=F.small, anchor="w", justify="left", wraplength=1000)
        self.notice.pack(anchor="w", padx=20, pady=(4, 0))
        self.only_attention = tk.BooleanVar(value=attention_only)
        theme.Check(self, "Needs attention only", self.only_attention, self.refresh).pack(anchor="w", padx=20, pady=(6, 8))

        buttons = theme.frame(self, theme.PANEL)
        buttons.pack(side="bottom", fill="x", padx=20, pady=16)
        Btn(buttons, "Use selected candidate", self.accept, variant="g").pack(side="left")
        Btn(buttons, "Choose another Rekordbox file…", self.choose).pack(side="left", padx=8)
        Btn(buttons, "Skip track", lambda: self.set_path(None), variant="r").pack(side="left")
        Btn(buttons, "Continue" if on_ready else "Export M3U8…", self.continue_action if on_ready else self.export, variant="g").pack(side="right")
        self.preview = Preview(self, self.preview_path)
        self.preview.pack(side="bottom", fill="x", padx=20)

        self.table = DataTable(self, [{"title": "Confidence", "width": 100, "kind": "meter"}, {"title": "Status", "width": 140, "kind": "chip"},
                                      {"title": "Spotify track", "weight": 1.2}, {"title": "Local file", "weight": 1.6, "kind": "monodim"}],
                               row_height=34)
        self.table.pack(fill="both", expand=True, padx=20)
        self.table.bind("<<TreeviewSelect>>", self.selection)
        self.options = DataTable(self, [{"title": "Source", "width": 150, "kind": "chip"}, {"title": "Format", "width": 64, "kind": "monodim"},
                                        {"title": "Bitrate", "width": 84, "kind": "monodim"}, {"title": "Length", "width": 70, "kind": "monodim"},
                                        {"title": "File", "weight": 1, "kind": "monodim"}], row_height=30)
        self.options.configure(height=150)
        self.options.grid_propagate(False)
        self.options.pack(side="bottom", fill="x", padx=20, pady=(8, 8))
        self.options.bind("<Double-Button-1>", lambda _: self.accept())
        theme.dark_titlebar(self)
        if on_ready:
            self.transient(app)
            self.grab_set()
        self.refresh()
        if self.table.iids():
            self.table.select([self.table.iids()[0]])

    def selected(self):
        selected = self.table.selection()
        return self.rows[int(selected[0])] if selected else None

    def auto_resolve(self):
        """Take the best-ranked Rekordbox candidate for every open track; skip tracks without one."""
        used = {path_key(r["path"]) for r in self.rows if r.get("path") and not needs_attention(r)}
        for row in self.rows:
            if not needs_attention(row):
                continue
            top = next((c for c in row["candidates"] if path_key(c["path"]) not in used), None)
            if top:
                used.add(path_key(top["path"]))
            row["path"] = top["path"] if top else None
            row["status"] = "chosen" if top else "skipped"
            row["confidence"] = confidence(row["track"], top)
        self.refresh()
        self.continue_action()

    def continue_action(self):
        open_rows = sum(needs_attention(row) for row in self.rows)
        if open_rows:
            if not self.on_ready:
                messagebox.showinfo("Check remaining tracks", "Accept a match or skip each remaining track before continuing.", parent=self)
                return
            choice = messagebox.ask_choice(
                "Tracks still need a decision",
                f"{open_rows} track{'s' if open_rows != 1 else ''} still need a match or a skip.\n\n"
                "Go back and decide yourself, or press Auto.",
                ("Go back", "Auto"), default=1, parent=self,
                tips=("Return to the list and decide each track yourself.",
                      "Takes the best-ranked Rekordbox file for every open track and skips the tracks that have no candidate."))
            if choice == 1:
                self.auto_resolve()
            return
        callback, rows = self.on_ready, self.rows
        self.destroy()
        callback(rows)

    def refresh(self):
        selected = self.table.selection()
        shown = []
        for index, row in enumerate(self.rows):
            if self.only_attention.get() and not needs_attention(row):
                continue
            track = row["track"]
            diagnostic = row.get("diagnostics", [])
            local = row["path"] or row.get("duplicate_of") or (diagnostic[0]["path"] if diagnostic else "")
            shown.append((str(index), [("meter", row["confidence"]), status_chip(row["status"]),
                                       ", ".join(track.get("artists", [])) + " — " + track["title"], local]))
        self.table.set_rows(shown)
        keep = [s for s in selected if self.table.exists(s)]
        if keep:
            self.table.select(keep, notify=False)
        elif shown:
            self.table.select([shown[0][0]])
        matched = sum(bool(r["path"]) for r in self.rows)
        suggested = sum(r["status"] == "suggested" for r in self.rows)
        duplicates = sum(r["status"] == "duplicate" for r in self.rows)
        self.summary.configure(text=f"{matched} selected ({suggested} suggestions) • {len(self.rows)-matched-duplicates} unmatched/skipped • "
                                    f"{duplicates} duplicates left out • {len(self.playlist.get('skipped', []))} unavailable Spotify items")

    def option_items(self, row):
        return row["candidates"] + row.get("diagnostics", [])

    def selection(self, _=None):
        self.preview.safe(self.preview.pause)
        row = self.selected()
        self.notice.configure(text="")
        rows, chosen = [], []
        if row:
            if row.get("diagnostics") and not row["path"]:
                self.notice.configure(text=row["status"] + ": " + row["diagnostics"][0]["path"] + "\nImport it into Rekordbox, re-export your collection XML, then rescan.")
            for index, item in enumerate(self.option_items(row)):
                source = ("chip", "g", "Rekordbox") if item.get("in_rekordbox") else ("chip", "a", "Preview only")
                rows.append((str(index), [source, item.get("format", ""), f"{round((item.get('bitrate') or 0)/1000)} kbps",
                                          f"{(item.get('duration_ms') or 0)/1000:.1f}s", item["path"]]))
                if item["path"] == row["path"]:
                    chosen.append(str(index))
        self.options.set_rows(rows)
        self.options.select(chosen, notify=False)

    def option_index(self):
        selected = self.options.selection()
        return int(selected[0]) if selected else None

    def preview_path(self):
        row = self.selected()
        if not row:
            return None
        index = self.option_index()
        options = self.option_items(row)
        return options[index]["path"] if index is not None and index < len(options) else row.get("path")

    def set_path(self, path):
        if path and (path_key(path) not in self.allowed_paths or not Path(path).is_file()):
            messagebox.showinfo("Not in Rekordbox", "This file is not available in your loaded Rekordbox collection. Import it into Rekordbox, re-export the collection XML, then rescan.", parent=self)
            return
        row = self.selected()
        if row and path:
            other = next((r for r in self.rows if r is not row and r.get("path") and path_key(r["path"]) == path_key(path)), None)
            if other:
                messagebox.showinfo("Already used", "This file is already used by “" + other["track"]["title"] + "” in this playlist. A file can appear only once per playlist.", parent=self)
                return
        if row:
            row.update(path=path, status="chosen" if path else "skipped")
            item = next((item for item in candidates(self.app.library, self.app.collection) if path and path_key(item["path"]) == path_key(path)), None)
            row["confidence"] = confidence(row["track"], item)
            self.app.answers[row["key"]] = path
            self.app.persist()
            self.refresh()
            self.selection()

    def accept(self):
        row, index = self.selected(), self.option_index()
        if row and index is not None:
            self.set_path(self.option_items(row)[index]["path"])
        elif row and row["path"]:
            self.set_path(row["path"])

    def choose(self):
        if self.selected():
            path = filedialog.askopenfilename(parent=self, filetypes=[("Audio", "*.mp3 *.flac *.wav *.aif *.aiff *.m4a *.mp4 *.ogg *.opus *.aac *.wma")])
            if path:
                self.set_path(path)

    def export(self):
        count = sum(bool(row["path"]) for row in self.rows)
        if not messagebox.askyesno("Confirm export", f"{count} songs to export · 0 to remove · {len(self.rows)-count} unmatched/skipped\nContinue?", parent=self):
            return
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", self.playlist["name"]).strip(". ") or "Playlist"
        path = filedialog.asksaveasfilename(parent=self, initialfile=name + ".m3u8", defaultextension=".m3u8", filetypes=[("Rekordbox playlist", "*.m3u8")])
        if path:
            try:
                count, missing = write_playlist(path, self.rows)
                messagebox.showinfo("Playlist exported", f"Saved {count} tracks; {missing} unmatched/skipped.\n\n{path}\n\nIn Rekordbox: File → Import → Import Playlist.", parent=self)
            except (OSError, ValueError) as error:
                messagebox.showerror("Export failed", str(error), parent=self)
