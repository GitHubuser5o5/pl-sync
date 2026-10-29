import sys
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import filedialog
import tomllib
import webbrowser

from spot2rb.core.library import scan
from spot2rb.core.rbimport import read_collection
from spot2rb.core.spotify import Spotify
from spot2rb.core import state
from spot2rb.ui import dialogs as messagebox
from spot2rb.ui import theme
from spot2rb.ui.queue import QueueScreen
from spot2rb.ui.theme import Btn, DataTable, F

BASE = Path(__file__).resolve().parents[1]
ASSETS = BASE / "assets"
TABS = ["Playlists", "Queue", "Connect"]


class App(tk.Tk):
    def __init__(self, autoload=True):
        super().__init__()
        theme.init(self)
        self.title("Spotify ↔ Rekordbox Playlist Companion")
        self.geometry("1000x720")
        self.minsize(760, 560)
        self.queue = Queue()
        self.busy = False
        self.spotify = None
        self.playlists = []
        self.fetched = []
        self.library = None
        self.collection = None
        self.answers = {}
        self.pairings = {}
        self.sync_queue = []
        self.exported = {}
        with (BASE / "config.toml").open("rb") as file:
            self.config = tomllib.load(file)["spotify"]
        self.status = tk.StringVar(value="Connect Spotify or scan your local library to begin.")
        self.load_icons()

        header = theme.frame(self, theme.CHASSIS)
        header.pack(fill="x", padx=20, pady=(14, 12))
        if self.logo_header:
            tk.Label(header, image=self.logo_header, bg=theme.CHASSIS, bd=0).pack(side="left", padx=(0, 14))
        tk.Label(header, text="Playlist Companion", font=F.title, fg=theme.LABEL, bg=theme.CHASSIS).pack(side="left", pady=(10, 0))
        self.tagline = tk.Label(header, text="FETCH PLAYLISTS • MATCH LOCAL FILES • EXPORT TO REKORDBOX", font=F.tag, fg=theme.DIM, bg=theme.CHASSIS)
        self.tagline.pack(side="right", pady=(18, 0))
        self.bind("<Configure>", self.on_resize)

        self.statusbar = theme.StatusBar(self, self.status)
        self.statusbar.pack(side="bottom", fill="x", pady=(12, 0))
        self.statusbar.set_level("idle")
        self.tabs = theme.TabStrip(self, TABS, self.show_page)
        self.tabs.pack(fill="x", padx=20)
        self.panel = theme.box(self, theme.PANEL)
        self.panel.pack(fill="both", expand=True, padx=20)

        self.playlist_page = theme.frame(self.panel, theme.PANEL, padx=16, pady=16)
        self.queue_screen = QueueScreen(self.panel, self)
        self.connect_page = theme.ScrollFrame(self.panel)
        self.pages = [self.playlist_page, self.queue_screen, self.connect_page]
        self.build_playlists(self.playlist_page)
        self.build_connect(self.connect_page.inner)
        self.show_page(0)

        self.restore()
        self.queue_screen.refresh()
        self.refresh_playlist_table()
        self.status.trace_add("write", self.status_changed)
        self.protocol("WM_DELETE_WINDOW", self.close)
        theme.dark_titlebar(self)
        self.poll_timer = self.after(100, self.poll)
        self.startup_timer = self.after(200, self.refresh_on_launch) if autoload else None

    # -- construction -------------------------------------------------------------
    def load_icons(self):
        self.logo_header = self.logo_icon = None
        try:
            self.logo_header = tk.PhotoImage(master=self, file=str(ASSETS / "logo_header.png"))
            # Window/taskbar icon: the supplied PL-SYNC icon (separate from the header logo)
            self.logo_icon = [tk.PhotoImage(master=self, file=str(ASSETS / f"icon_{n}.png")) for n in (256, 64, 32, 16)]
            self.iconphoto(True, *self.logo_icon)
        except tk.TclError:
            pass

    def on_resize(self, event):
        if event.widget is self:
            if event.width < 880:
                self.tagline.pack_forget()
            elif not self.tagline.winfo_ismapped():
                self.tagline.pack(side="right", pady=(18, 0))

    def show_page(self, index):
        for page in self.pages:
            page.pack_forget()
        self.pages[index].pack(fill="both", expand=True)

    def build_playlists(self, page):
        top = theme.frame(page)
        top.pack(fill="x", pady=(0, 12))
        theme.dim(top, "Select a Spotify playlist.").pack(side="left")
        self.hidden_text = tk.StringVar()
        self.search = tk.StringVar()
        clear = Btn(top, "Clear", lambda: (self.search.set(""), self.search_entry.focus_set()), small=True, minwidth=0)
        clear.pack(side="right", padx=(8, 0))
        self.search_entry = theme.entry(top, self.search, width=28)
        self.search_entry.pack(side="right", ipady=3)
        theme.Cap(top, "Search").pack(side="right", padx=(0, 8))
        self.search.trace_add("write", lambda *_: self.refresh_playlist_table())
        self.search_entry.bind("<Escape>", lambda e: self.search.set(""))
        self.search_entry.bind("<Down>", lambda e: (self.playlist_table.focus_set(), "break")[1])
        actions = theme.frame(page)
        actions.pack(side="bottom", fill="x", pady=(12, 0))
        tk.Label(actions, textvariable=self.hidden_text, bg=theme.PANEL, fg=theme.DIM, font=F.small, anchor="w").pack(side="left")
        self.export_button = Btn(actions, "Export", lambda: self.prepare_playlist(False), variant="g")
        self.export_button.pack(side="right")
        self.queue_button = Btn(actions, "Add to queue", lambda: self.prepare_playlist(True), variant="a")
        self.queue_button.pack(side="right", padx=8)
        self.preview_button = Btn(actions, "Preview playlist", lambda: self.fetch_selected(self.show_tracks))
        self.preview_button.pack(side="right")
        self.playlist_table = DataTable(page, [{"title": "Playlist", "weight": 1}, {"title": "Tracks", "width": 90, "kind": "monodim"},
                                              {"title": "Marker", "width": 150, "kind": "chip"}], row_height=34)
        self.playlist_table.pack(fill="both", expand=True)
        self.empty_box = theme.frame(self.playlist_table.body, theme.WELL)
        self.empty_text = tk.StringVar(value="Log in to load your playlists")
        tk.Label(self.empty_box, textvariable=self.empty_text, bg=theme.WELL, fg=theme.DIM, font=F.body).pack(side="left", padx=(0, 14))
        self.empty_button = Btn(self.empty_box, "Go to Connect", lambda: self.tabs.select(2), small=True)
        self.empty_button.pack(side="left")

    def path_row(self, parent, caption, variable, button_text, command):
        theme.Cap(parent, caption).pack(anchor="w", pady=(0, 4))
        row = theme.frame(parent)
        row.pack(fill="x", pady=(0, 12))
        button = Btn(row, button_text, command)
        button.pack(side="right", padx=(8, 0))
        theme.entry(row, variable).pack(side="left", fill="x", expand=True, ipady=5)
        return button

    def build_connect(self, page):
        wrap = theme.frame(page, theme.PANEL, padx=16, pady=16)
        wrap.pack(fill="both", expand=True)

        spotify = theme.Zone(wrap, "Spotify")
        spotify.pack(fill="x", pady=(0, 12))
        pair = theme.frame(spotify.body)
        pair.pack(fill="x")
        pair.grid_columnconfigure(0, weight=1, uniform="c")
        pair.grid_columnconfigure(1, weight=1, uniform="c")
        left = theme.frame(pair)
        left.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        theme.Cap(left, "Spotify Client ID").pack(anchor="w", pady=(0, 4))
        self.client_id = tk.StringVar(value=self.config.get("client_id", ""))
        theme.entry(left, self.client_id).pack(fill="x", ipady=5)
        right = theme.frame(pair)
        right.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        theme.Cap(right, "Redirect URI to register in your Spotify app").pack(anchor="w", pady=(0, 4))
        uri = tk.StringVar(value=self.config["redirect_uri"])
        line = theme.frame(right)
        line.pack(fill="x")
        Btn(line, "Copy", lambda: (self.clipboard_clear(), self.clipboard_append(uri.get()), self.status.set("Redirect URI copied.")),
            small=True).pack(side="right", padx=(8, 0))
        redirect = theme.entry(line, uri)
        redirect.configure(state="readonly")
        redirect.pack(side="left", fill="x", expand=True, ipady=5)
        bottom = theme.frame(spotify.body)
        bottom.pack(fill="x", pady=(12, 0))
        self.login_button = Btn(bottom, "Log in and load playlists", self.login, variant="g")
        self.login_button.pack(side="right", padx=(12, 0))
        tk.Label(bottom, text="Development mode needs an app owner with Premium. Only owned or collaborative playlist contents are accessible.",
                 bg=theme.PANEL, fg=theme.DIM, font=F.small, justify="left", anchor="w", wraplength=520).pack(side="left", fill="x", expand=True)

        library = theme.Zone(wrap, "Library")
        library.pack(fill="x", pady=(0, 12))
        self.folder = tk.StringVar()
        self.path_row(library.body, "Music folder (optional, detects files not imported into Rekordbox only)", self.folder,
                      "Choose music folder…", self.choose_folder)
        self.search_sub = tk.BooleanVar(value=False)
        self.sub_include = None
        sub_row = theme.frame(library.body)
        sub_row.pack(fill="x", pady=(0, 12))
        theme.Switch(sub_row, "Also search subfolders", self.search_sub, self.update_sub).pack(side="left")
        self.sub_button = Btn(sub_row, "Choose subfolders…", self.choose_subfolders, small=True)
        self.sub_button.pack(side="left", padx=(14, 14))
        self.sub_label = tk.Label(sub_row, bg=theme.PANEL, fg=theme.DIM, font=F.mono, anchor="w")
        self.sub_label.pack(side="left")
        self.xml = tk.StringVar()
        self.path_row(library.body, "Rekordbox collection XML (required for playlist export)", self.xml, "Choose XML…",
                      lambda: self.choose(self.xml, False))
        self.scan_button = Btn(library.body, "Scan local library", self.scan, variant="g")
        self.scan_button.pack(anchor="e")
        self.update_sub()

        output = theme.Zone(wrap, "Output")
        output.pack(fill="x")
        self.output_dir = tk.StringVar()
        self.path_row(output.body, "Download folder (exported M3U8 playlists are saved here)", self.output_dir, "Choose download folder…",
                      lambda: self.choose(self.output_dir, True))

    # -- status / busy ------------------------------------------------------------
    def status_changed(self, *_):
        text = self.status.get().lower()
        if any(word in text for word in ("could not", "failed", "denied", "unavailable")):
            level = "error"
        elif any(word in text for word in ("issues", "wait", "login again")):
            level = "warn"
        else:
            level = "ok"
        self.statusbar.set_level(level)

    def set_busy(self, busy):
        self.busy = busy
        self.statusbar.set_busy(busy)
        for button in (self.preview_button, self.queue_button, self.export_button, self.login_button, self.scan_button):
            button.configure(state="disabled" if busy else "normal")

    def hidden_note(self):
        hidden = getattr(self.spotify, "hidden", 0)
        return f" {hidden} playlists you neither own nor collaborate on are hidden (Spotify blocks their contents)." if hidden else ""

    def update_hidden_label(self):
        hidden = getattr(self.spotify, "hidden", 0)
        self.hidden_text.set(f"{hidden} followed or saved playlists hidden (Spotify only shares owned or collaborative)" if hidden else "")

    # -- playlists table ------------------------------------------------------------
    def snapshot_of(self, playlist_id):
        for playlist in self.playlists:
            if playlist["id"] == playlist_id:
                return playlist.get("snapshot_id")
        return None

    def marker(self, playlist):
        items = [item for item in self.sync_queue if item.get("spotify_id") == playlist["id"]]
        if any(item.get("status") in ("Queued", "Processing") for item in items):
            return ("chip", "n", "Queued")
        done = [item.get("snapshot_id") for item in items if str(item.get("status", "")).startswith("Exported")]
        if playlist["id"] in self.exported:
            done.append(self.exported[playlist["id"]])
        if not done:
            return ""
        current, known = playlist.get("snapshot_id"), [d for d in done if d]
        if current and known and current not in known:
            return ("chip", "a", "Changed")
        return ("chip", "g", "Exported")

    def selected_ids(self):
        return [self.playlists[int(i)]["id"] for i in self.playlist_table.selection() if int(i) < len(self.playlists)]

    def refresh_playlist_table(self, keep=None):
        if keep is None:
            keep = self.selected_ids()
        rows = []
        needle = self.search.get().strip().casefold()
        for index, playlist in enumerate(self.playlists):
            if needle and needle not in playlist["name"].casefold():
                continue
            total = (playlist.get("tracks") or {}).get("total", (playlist.get("items") or {}).get("total"))
            rows.append((str(index), [playlist["name"], "—" if total is None else str(total), self.marker(playlist)]))
        self.playlist_table.set_rows(rows)
        self.playlist_table.select([str(i) for i, p in enumerate(self.playlists) if p["id"] in keep], notify=False)
        if rows:
            self.empty_box.place_forget()
        else:
            searching = bool(self.playlists)
            self.empty_text.set(f"No playlists match “{self.search.get().strip()}”" if searching else "Log in to load your playlists")
            if searching:
                self.empty_button.pack_forget()
            elif not self.empty_button.winfo_ismapped():
                self.empty_button.pack(side="left")
            self.empty_box.place(relx=.5, y=40, anchor="n")
        self.update_hidden_label()

    def selected_playlist_index(self):
        selected = self.playlist_table.selection()
        return int(selected[0]) if selected else None

    def set_playlists(self, playlists, keep=None):
        self.playlists = playlists
        self.refresh_playlist_table(keep if keep is not None else [])

    def mark_exported(self, playlist_id, snapshot_id=None):
        if playlist_id:
            self.exported[playlist_id] = snapshot_id or self.snapshot_of(playlist_id)
        self.refresh_playlist_table()

    # -- lifecycle ------------------------------------------------------------------
    def destroy(self):
        if getattr(self, "startup_timer", None):
            self.after_cancel(self.startup_timer)
            self.startup_timer = None
        if getattr(self, "poll_timer", None):
            self.after_cancel(self.poll_timer)
            self.poll_timer = None
        super().destroy()

    def refresh_on_launch(self):
        self.startup_timer = None
        folder, xml, client = self.folder.get().strip(), self.xml.get().strip(), self.spotify
        if not folder and not xml and not client:
            self.status.set("Choose your Rekordbox XML and log in once. Future launches will refresh automatically.")
            return
        sub_scan = self.scan_folder
        def work():
            result, errors = {}, []
            for name, action in [
                ("library", lambda: sub_scan(folder) if folder else None),
                ("collection", lambda: read_collection(xml) if xml else None),
                ("playlists", lambda: client.playlists() if client else None),
            ]:
                try:
                    value = action()
                    if value is not None:
                        result[name] = value
                except Exception as error:
                    errors.append(f"{name}: {error}")
            return result, errors
        def done(outcome):
            result, errors = outcome
            keep = self.selected_ids()
            for name, value in result.items():
                if name != "playlists":
                    setattr(self, name, value)
            if "playlists" in result:
                self.set_playlists(result["playlists"], keep)
            if errors:
                self.status.set("Refresh finished with issues: " + " | ".join(errors))
                messagebox.showwarning("Some sources could not refresh", "Saved data was kept for failed sources.\n\n" + "\n".join(errors))
            else:
                self.status.set("Startup refresh finished. Libraries are ready." + (" Log in to Spotify to refresh it too." if not client else "") + self.hidden_note())
        self.run("Refreshing your local and Spotify libraries…", work, done)

    def persist(self):
        try:
            state.save(BASE / "data" / "session.json", {
                "client_id": self.client_id.get(), "folder": self.folder.get(), "xml": self.xml.get(),
                "output_dir": self.output_dir.get(),
                "search_sub": self.search_sub.get(), "sub_include": self.sub_include,
                "playlists": self.playlists, "fetched": self.fetched,
                "library": self.library, "collection": self.collection, "answers": self.answers,
                "pairings": self.pairings, "sync_queue": self.sync_queue, "exported": self.exported,
                "selected": [int(i) for i in self.playlist_table.selection()]})
            if self.spotify and self.spotify.token:
                state.save_login(BASE / "data" / "login.json", self.spotify.client_id, self.spotify.token)
            return True
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not save session", str(error))
            return False

    def close(self):
        if self.busy or self.queue_screen.running:
            messagebox.showinfo("Work in progress", "Wait for the current operation to finish before closing so its results can be saved.")
            return
        if self.persist():
            self.destroy()

    def restore(self):
        try:
            saved = state.load(BASE / "data" / "session.json")
            for name in ("client_id", "folder", "xml", "output_dir"):
                if name in saved:
                    getattr(self, name).set(saved[name])
            self.search_sub.set(bool(saved.get("search_sub", False)))
            include = saved.get("sub_include")
            self.sub_include = list(include) if isinstance(include, list) else None
            self.update_sub()
            for name in ("playlists", "fetched", "library", "collection", "answers", "pairings", "sync_queue", "exported"):
                if name in saved:
                    setattr(self, name, saved[name])
            if isinstance(self.exported, list):  # older sessions stored a plain list of ids
                self.exported = {playlist_id: None for playlist_id in self.exported}
            self.refresh_playlist_table([])
            self.playlist_table.select([str(i) for i in saved.get("selected", []) if isinstance(i, int) and i < len(self.playlists)], notify=False)
            self.show_library()
            if saved:
                self.status.set("Saved session restored. Rescan after changing your music files or collection XML.")
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.status.set(f"Could not restore saved session: {error}")
        try:
            login = state.load_login(BASE / "data" / "login.json")
            if login and login["client_id"] == self.client_id.get().strip():
                self.spotify = Spotify(login["client_id"], self.config["redirect_uri"])
                self.spotify.token = login["token"]
        except (OSError, ValueError, KeyError):
            self.status.set("Session restored. Please log in to Spotify again.")

    # -- library settings -----------------------------------------------------------
    def update_sub(self):
        on = self.search_sub.get()
        self.sub_button.configure(state="normal" if on else "disabled")
        if not on:
            self.sub_label.configure(text="Only the music folder itself is searched")
        elif self.sub_include is None:
            self.sub_label.configure(text="All subfolders")
        else:
            self.sub_label.configure(text=f"{len(self.sub_include)} subfolder(s) selected" if self.sub_include else "No subfolders selected")

    def choose_folder(self):
        before = self.folder.get()
        self.choose(self.folder, True)
        if self.folder.get() != before:
            self.sub_include = None
            self.update_sub()

    def choose_subfolders(self):
        root = Path(self.folder.get().strip())
        if not root.is_dir():
            messagebox.showinfo("Choose a music folder", "Choose an existing music folder first.")
            return
        names = sorted((p.name for p in root.iterdir() if p.is_dir()), key=str.casefold)
        if not names:
            messagebox.showinfo("No subfolders", "This music folder has no subfolders.")
            return
        dialog = tk.Toplevel(self)
        theme.init(dialog)
        dialog.title("Choose subfolders")
        dialog.geometry("420x460")
        dialog.configure(bg=theme.PANEL)
        dialog.transient(self)
        theme.dark_titlebar(dialog)
        tk.Label(dialog, text="Search only these subfolders (including what is inside them):", bg=theme.PANEL, fg=theme.LABEL,
                 font=F.body, wraplength=380, justify="left", anchor="w").pack(anchor="w", padx=20, pady=(16, 10))
        table = DataTable(dialog, [{"title": "", "width": 20, "kind": "check"}, {"title": "Folder", "weight": 1}], mode="multiple", row_height=30)
        table.pack(fill="both", expand=True, padx=20)
        chosen = set(names if self.sub_include is None else self.sub_include)
        counter = tk.StringVar()
        def rebuild(selection=None):
            if selection is not None:
                chosen.clear()
                chosen.update(names[int(i)] for i in selection)
            table.set_rows([(str(i), [("check", name in chosen), name]) for i, name in enumerate(names)])
            table.select([str(i) for i, name in enumerate(names) if name in chosen], notify=False)
            counter.set(f"{len(chosen)} of {len(names)}")
        table.bind("<<TreeviewSelect>>", lambda e: rebuild(table.selection()))
        def set_all(value):
            chosen.clear()
            if value:
                chosen.update(names)
            rebuild()
        def apply():
            picked = [n for n in names if n in chosen]
            self.sub_include = None if len(picked) == len(names) else picked
            self.update_sub()
            self.status.set("Subfolder choice changed. Press Scan local library to apply it.")
            dialog.destroy()
        tools = theme.frame(dialog, theme.PANEL)
        tools.pack(fill="x", padx=20, pady=(10, 0))
        Btn(tools, "Select all", lambda: set_all(True), small=True).pack(side="left")
        Btn(tools, "Select none", lambda: set_all(False), small=True).pack(side="left", padx=8)
        tk.Label(tools, textvariable=counter, bg=theme.PANEL, fg=theme.DIM, font=F.mono).pack(side="right")
        buttons = theme.frame(dialog, theme.PANEL)
        buttons.pack(fill="x", padx=20, pady=16)
        Btn(buttons, "OK", apply, variant="g", minwidth=80).pack(side="right")
        Btn(buttons, "Cancel", dialog.destroy, minwidth=80).pack(side="right", padx=8)
        rebuild()
        dialog.grab_set()

    def scan_folder(self, folder):
        return scan(folder, BASE / "data" / "library.sqlite3", self.search_sub.get(), self.sub_include)

    # -- windows --------------------------------------------------------------------
    def show_tracks(self, playlist=None):
        if playlist is None:
            return
        preview = tk.Toplevel(self)
        theme.init(preview)
        preview.title("Preview playlist - " + playlist["name"])
        preview.geometry("900x550")
        preview.configure(bg=theme.PANEL)
        theme.dark_titlebar(preview)
        tk.Label(preview, text=f"{playlist['name']} - {len(playlist['tracks'])} tracks", font=F.h2, bg=theme.PANEL, fg=theme.LABEL,
                 anchor="w").pack(anchor="w", padx=20, pady=(16, 10))
        theme.dim(preview, f"{len(playlist.get('skipped', []))} unavailable/non-music items skipped").pack(side="bottom", anchor="w", padx=20, pady=(8, 16))
        table = DataTable(preview, [{"title": "Title", "weight": 2}, {"title": "Artists", "weight": 1.4}, {"title": "Album", "weight": 1.4},
                                    {"title": "Year", "width": 56, "kind": "monodim"}, {"title": "ISRC", "width": 130, "kind": "monodim"}])
        table.pack(fill="both", expand=True, padx=20)
        table.set_rows([(str(i), [t["title"], ", ".join(t["artists"]), t.get("album", ""), str(t.get("year", "")), t.get("isrc") or ""])
                        for i, t in enumerate(playlist["tracks"])])

    def show_library(self):
        local = self.library or {"tracks": [], "errors": []}
        rb = self.collection or {"tracks": {}, "playlists": []}
        self.status.set(f"Scanned {len(rb['tracks'])} Rekordbox tracks and {len(local['tracks'])} local files. {len(local['errors'])} scan errors.")

    def choose(self, variable, folder):
        value = filedialog.askdirectory() if folder else filedialog.askopenfilename(filetypes=[("Rekordbox XML", "*.xml")])
        if value:
            variable.set(value)

    def run(self, message, work, done, on_error=None):
        if self.busy:
            messagebox.showinfo("Work in progress", "Please wait for the current operation to finish.")
            return
        self.set_busy(True)
        self.status.set(message)
        def worker():
            try:
                self.queue.put((done, work(), None, on_error))
            except Exception as error:
                self.queue.put((done, None, str(error), on_error))
        Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            done, result, error, on_error = self.queue.get_nowait()
            self.set_busy(False)
            if error:
                self.status.set(error)
                self.statusbar.set_level("error")
                if on_error:
                    on_error(error)
                else:
                    messagebox.showerror("Could not complete operation", error)
            else:
                done(result)
                self.persist()
            self.queue_screen.refresh()
            self.refresh_playlist_table()
        except Empty:
            pass
        self.poll_timer = self.after(100, self.poll)

    def login(self):
        client_id = self.client_id.get()
        def work():
            client = self.spotify
            if not client or client.client_id != client_id.strip():
                client = Spotify(client_id, self.config["redirect_uri"])
                client.login(webbrowser.open)
            return client, client.playlists()
        def done(result):
            self.spotify = result[0]
            self.set_playlists(result[1])
            self.status.set(f"Connected. {len(self.playlists)} playlists listed." + self.hidden_note())
        self.run("Waiting for Spotify login in your browser (up to 3 minutes)…", work, done)

    def fetch_selected(self, on_ready):
        if self.busy or self.queue_screen.running:
            messagebox.showinfo("Work in progress", "Wait for the current operation to finish.")
            return
        index = self.selected_playlist_index()
        if not self.spotify or index is None:
            messagebox.showinfo("Select a playlist", "Log in and select a Spotify playlist first.")
            return
        playlist = dict(self.playlists[index])
        client = self.spotify
        def work():
            return dict(client.tracks(playlist["id"]), name=playlist["name"])
        def done(result):
            self.fetched = [p for p in self.fetched if p["playlist_id"] != result["playlist_id"]] + [result]
            self.status.set(f"Loaded {len(result['tracks'])} tracks from {result['name']}.")
            on_ready(result)
        self.run("Loading playlist: " + playlist["name"], work, done)

    def scan(self):
        folder, xml = self.folder.get().strip(), self.xml.get().strip()
        if not folder and not xml:
            messagebox.showinfo("Choose a source", "Choose a music folder or Rekordbox collection XML.")
            return
        def work():
            return (self.scan_folder(folder) if folder else None,
                    read_collection(xml) if xml else None)
        def done(result):
            self.library, self.collection = result
            self.show_library()
        self.run("Reading audio tags and Rekordbox XML…", work, done)

    def prepare_playlist(self, queued):
        if self.busy or self.queue_screen.running:
            messagebox.showinfo("Work in progress", "Wait for the current operation to finish.")
            return
        if self.collection is None or not self.collection.get("sha256"):
            messagebox.showinfo("Scan first", "Choose and scan your Rekordbox collection XML first.")
            return
        from spot2rb.ui.import_dialog import ImportDialog
        self.fetch_selected(lambda playlist: ImportDialog(self, playlist, queued))


def main():
    App().mainloop()
