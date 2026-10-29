"""A list of reviewed tasks and a Start button."""
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog

from spot2rb.core.tasks import execute
from spot2rb.ui import dialogs as messagebox
from spot2rb.ui import theme
from spot2rb.ui.theme import Btn, DataTable


class QueueScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.PANEL, bd=0, highlightthickness=0, padx=16, pady=16)
        self.app, self.running = app, False
        buttons = theme.frame(self)
        buttons.pack(side="bottom", fill="x", pady=(12, 0))
        self.start_button = Btn(buttons, "Start queue", self.start, variant="g")
        self.start_button.pack(side="right")
        self.clear_button = Btn(buttons, "Clear", self.clear)
        self.clear_button.pack(side="right", padx=8)
        theme.dim(buttons, "Select tasks and press Delete or Backspace to remove them.", font=theme.F.small).pack(side="left")
        self.table = DataTable(self, [{"title": "Playlist", "weight": 1}, {"title": "Task", "weight": 1.3},
                                      {"title": "Status", "width": 170, "kind": "chip"}], mode="extended", row_height=34,
                               empty_text="Nothing queued. Use Add to queue in Playlists.")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<Delete>", self.remove_selected)
        self.table.bind("<BackSpace>", self.remove_selected)

    @staticmethod
    def chip(status):
        head = re.split(r" — |: ", status, 1)[0]
        if status.startswith("Exported"):
            return ("chip", "g", "Exported")
        if status.startswith("Failed"):
            return ("chip", "r", "Failed")
        if status == "Processing":
            return ("chip", "a", "Processing", True)
        if status == "Queued":
            return ("chip", "n", "Queued")
        return ("chip", "d", head[:18])

    def refresh(self):
        rows = []
        for item in self.app.sync_queue:
            if item.get("mode") == "new":
                action = "New playlist: " + item.get("playlist_name", item["name"])
                status = item.get("status", "Queued") if item.get("schema") == 2 else "Old task — add again from Playlists"
            else:
                action = "Add to existing playlist (no longer supported)"
                status = "Not exported — XML export was removed, delete this task"
            rows.append((item["id"], [item["name"], action, self.chip(status)]))
        self.table.set_rows(rows)

    def remove_selected(self, event=None):
        if self.running:
            return "break"
        selected = set(self.table.selection())
        if selected:
            self.app.sync_queue = [item for item in self.app.sync_queue if item["id"] not in selected]
            self.app.persist()
            self.refresh()
            self.app.refresh_playlist_table()
        return "break"

    def clear(self):
        if self.running or not self.app.sync_queue:
            return
        if messagebox.askyesno("Clear queue", f"Remove all {len(self.app.sync_queue)} tasks from the queue?", parent=self, danger=True):
            self.app.sync_queue = []
            self.app.persist()
            self.refresh()
            self.app.refresh_playlist_table()

    def download_folder(self):
        folder = self.app.output_dir.get().strip()
        if folder and Path(folder).is_dir():
            return Path(folder)
        chosen = filedialog.askdirectory(title="Choose the download folder for exported playlists")
        if chosen:
            self.app.output_dir.set(chosen)
        return Path(chosen) if chosen else None

    def start(self):
        if self.running or self.app.busy:
            return
        self.pending = [item for item in self.app.sync_queue
                        if item.get("schema") == 2 and item.get("mode") == "new" and item.get("status") == "Queued"]
        if not self.pending:
            messagebox.showinfo("Queue", "No pending tasks. Use Add to queue in Playlists.")
            return
        output = self.download_folder()
        if not output:
            return
        self.output = output
        self.running, self.index = True, 0
        self.used_names = set()
        self.start_button.configure(state="disabled")
        self.clear_button.configure(state="disabled")
        self.next_item()

    def end_run(self):
        self.running = False
        self.start_button.configure(state="normal")
        self.clear_button.configure(state="normal")

    def next_item(self):
        if self.index >= len(self.pending):
            self.end_run()
            self.app.status.set(f"Queue finished. Playlists saved in {self.output}; import them in Rekordbox (File → Import → Import Playlist).")
            self.app.refresh_playlist_table()
            return
        item = self.pending[self.index]
        self.index += 1
        item["status"] = "Processing"
        self.refresh()
        self.app.status.set(f"Processing {self.index}/{len(self.pending)}: {item['name']}")
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", item["playlist_name"]).strip(". ") or "Playlist"
        filename, counter = name + ".m3u8", 2
        while filename.casefold() in self.used_names:
            filename = f"{name}-{counter}.m3u8"
            counter += 1
        self.used_names.add(filename.casefold())
        output = self.output / filename
        def work():
            execute(item, self.app.collection, output)
        def done(_):
            item.update(status="Exported — import into Rekordbox", output=str(output))
            self.finish_item()
        def failed(error):
            item["status"] = "Failed: " + error
            self.finish_item()
        self.app.run("Exporting queued playlist…", work, done, on_error=failed)

    def finish_item(self):
        self.app.persist()
        self.refresh()
        self.after(100, self.next_item)
