from copy import deepcopy
from threading import Thread
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import uuid
import re

from spot2rb.core.matcher import candidates
from spot2rb.core.review import build_rows, needs_attention
from spot2rb.core.tasks import execute
from spot2rb.ui import dialogs as messagebox
from spot2rb.ui import theme
from spot2rb.core.missing import missing_rows
from spot2rb.ui.export import ExportWindow
from spot2rb.ui.missing import MissingWindow
from spot2rb.ui.theme import Btn, BusyOverlay, F


class ImportDialog(tk.Toplevel):
    """Name the new M3U8 playlist, then review unsure matches before exporting or queueing."""

    def __init__(self, app, playlist, queued):
        super().__init__(app)
        theme.init(self)
        self.app, self.playlist, self.queued = app, playlist, queued
        self.title("Add to queue" if queued else "Export playlist")
        self.geometry("480x240")
        self.minsize(400, 220)
        self.configure(bg=theme.PANEL)
        self.transient(app)
        theme.dark_titlebar(self)
        self.grab_set()
        self.name = tk.StringVar(value=playlist["name"])
        tk.Label(self, text=playlist["name"], font=F.h2, bg=theme.PANEL, fg=theme.LABEL, anchor="w").pack(anchor="w", padx=20, pady=(18, 10))
        theme.Cap(self, "Playlist name (saved as an M3U8 file)").pack(anchor="w", padx=20, pady=(0, 4))
        self.name_entry = theme.entry(self, self.name)
        self.name_entry.pack(fill="x", padx=20, ipady=5)
        self.name_entry.bind("<Return>", lambda _: self.continue_action())
        self.name_entry.focus_set()
        theme.dim(self, "Files still need to be imported into Rekordbox manually.", font=F.small).pack(anchor="w", padx=20, pady=10)
        buttons = theme.frame(self, theme.PANEL)
        buttons.pack(side="bottom", fill="x", padx=20, pady=16)
        Btn(buttons, "Continue", self.continue_action, variant="g").pack(side="right")
        Btn(buttons, "Cancel", self.destroy).pack(side="right", padx=8)

    def continue_action(self):
        name = self.name.get().strip()
        if not name:
            return
        self.task = {"schema": 2, "id": uuid.uuid4().hex, "mode": "new", "name": self.playlist["name"],
                     "playlist_name": name, "destination": None, "source_hash": self.app.collection["sha256"],
                     "status": "Queued", "spotify_id": self.playlist.get("playlist_id"),
                     "snapshot_id": self.app.snapshot_of(self.playlist.get("playlist_id"))}
        self.withdraw()
        self.grab_release()
        overlay = BusyOverlay(self.app, "Matching tracks…")
        outcome = {}

        def work():
            try:
                outcome["files"] = candidates(self.app.library, self.app.collection)
                outcome["rows"] = build_rows(self.playlist, self.app.library, self.app.collection, self.app.answers)
            except Exception as error:
                outcome["error"] = error

        thread = Thread(target=work, daemon=True)
        thread.start()
        self.wait_for(thread, overlay, outcome)

    def wait_for(self, thread, overlay, outcome):
        if thread.is_alive():
            self.after(50, lambda: self.wait_for(thread, overlay, outcome))
            return
        overlay.close()
        if "error" in outcome:
            self.deiconify()
            self.grab_set()
            messagebox.showerror("Could not prepare playlist", str(outcome["error"]), parent=self)
            return
        rows = outcome["rows"]
        if any(needs_attention(row) for row in rows):
            review = ExportWindow(self.app, self.playlist, attention_only=True, on_ready=self.finish, rows=rows, files=outcome["files"])
            review.protocol("WM_DELETE_WINDOW", lambda: (review.destroy(), self.destroy()))
        else:
            self.finish(rows)

    def finish(self, rows):
        task = self.task
        task["rows"] = deepcopy(rows)
        try:
            adds = sum(bool(r["path"]) for r in rows)
            holes = missing_rows(rows)
            list_tip = "Songs with no downloaded file, as a list you can save as TXT."
            if not adds:
                while holes and messagebox.ask_choice(
                        "No matched tracks", "There are no selected Rekordbox files to export. Import the missing music into Rekordbox and rescan first.",
                        ("Close", "Missing list…"), default=1, parent=self.app, tips=(None, list_tip)) == 1:
                    MissingWindow(self.app, self.playlist["name"], rows).wait_window()
                if not holes:
                    messagebox.showinfo("No matched tracks", "There are no selected Rekordbox files to export. Import the missing music into Rekordbox and rescan first.", parent=self.app)
                self.destroy()
                return
            missing = sum(not r["path"] for r in rows) + len(self.playlist.get("skipped", []))
            action = "Add to queue" if self.queued else "Export"
            buttons = ["Cancel"] + (["Missing list…"] if holes else []) + [action]
            tips = [None] + ([list_tip] if holes else []) + [None]
            while True:
                choice = buttons[messagebox.ask_choice("Confirm playlist", f"{adds} songs to add · {missing} unmatched/skipped\n\n{action}?",
                                                       buttons, default=len(buttons) - 1, parent=self.app, tips=tips)]
                if choice != "Missing list…":
                    break
                MissingWindow(self.app, self.playlist["name"], rows).wait_window()
            if choice != action:
                self.destroy()
                return
            if self.queued:
                self.app.sync_queue.append(task)
                self.app.queue_screen.refresh()
                self.app.persist()
                self.app.status.set(f"Added to queue: {task['name']}")
            else:
                filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", task["playlist_name"]).strip(". ") or "Playlist"
                folder = self.app.output_dir.get().strip()
                if folder and Path(folder).is_dir():
                    output = str(Path(folder) / (filename + ".m3u8"))
                else:
                    output = filedialog.asksaveasfilename(parent=self.app, initialfile=filename + ".m3u8", defaultextension=".m3u8", filetypes=[("Playlist file", "*.m3u8")])
                if output:
                    execute(task, self.app.collection, output)
                    self.app.mark_exported(task.get("spotify_id"))
                    messagebox.showinfo("Exported", f"Saved: {output}\n\nIn Rekordbox: File → Import → Import Playlist.", parent=self.app)
            self.destroy()
        except (ValueError, OSError) as error:
            messagebox.showerror("Could not prepare playlist", str(error), parent=self.app)
            self.destroy()
