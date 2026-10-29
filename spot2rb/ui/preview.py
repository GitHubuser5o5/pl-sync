import tkinter as tk

from spot2rb.ui import theme
from spot2rb.ui.theme import Btn, Seek
from spot2rb.core.audio import AudioPreview, prepare_audio
from concurrent.futures import ThreadPoolExecutor


class Preview(tk.Frame):
    def __init__(self, parent, get_path):
        super().__init__(parent, bg=theme.PANEL, bd=0, highlightthickness=0)
        self.get_path, self.player = get_path, None
        self.timer = None
        self.dragging = False
        self.loader = ThreadPoolExecutor(max_workers=1)
        self.loading = None
        self.load_timer = None
        self.original_path = None
        self.temporary = None
        self.playing = False
        self.button = Btn(self, "▶ Preview", lambda: self.safe(self.toggle), variant="a", minwidth=110)
        self.button.pack(side="left")
        self.seekbar = Seek(self, from_=0, to=1)
        self.seekbar.pack(side="left", fill="x", expand=True, padx=8)
        self.seekbar.bind("<ButtonPress-1>", lambda _: setattr(self, "dragging", True))
        self.seekbar.bind("<ButtonRelease-1>", lambda _: self.safe(self.seek))
        self.label = tk.Label(self, text="Select a file to preview", bg=theme.PANEL, fg=theme.DIM, font=theme.F.mono, width=40,
                              anchor="w", justify="left")
        self.label.pack(side="left")
        self.bind("<Destroy>", self.cleanup)

    def safe(self, action):
        try:
            action()
        except (OSError, ValueError, RuntimeError) as error:
            self.label.configure(text="Preview unavailable: " + str(error))

    def toggle(self):
        if self.playing:
            self.pause()
        else:
            self.play()

    def play(self):
        path = self.get_path()
        if not path or self.loading:
            return
        if path != self.original_path:
            self.pause()
            self.label.configure(text="Preparing audio preview…")
            self.loading = self.loader.submit(prepare_audio, path)
            self.pending_path = path
            self.check_load()
            return
        self.start_player()

    def check_load(self):
        self.load_timer = None
        if not self.loading.done():
            self.load_timer = self.after(100, self.check_load)
            return
        future, self.loading = self.loading, None
        try:
            path, temporary = future.result()
            if self.get_path() != self.pending_path:
                if temporary:
                    temporary.cleanup()
                self.label.configure(text="Selection changed — press Preview for this file")
                return
            if self.player:
                self.player.close()
            if self.temporary:
                self.temporary.cleanup()
            self.temporary = temporary
            self.player = AudioPreview()
            self.player.load(path)
            self.original_path = self.pending_path
            self.start_player()
        except Exception as error:
            self.original_path = None
            self.label.configure(text="Preview unavailable: " + str(error))

    def start_player(self):
        self.player.play()
        self.playing = True
        self.button.configure(text="Pause")
        self.seekbar.configure(to=max(1, self.player.length()))
        if self.timer is None:
            self.tick()

    def tick(self):
        self.timer = None
        if self.player and self.player.path:
            try:
                position, length = self.player.position(), self.player.length()
                if not self.dragging:
                    self.seekbar.set(position)
                self.label.configure(text=f"{position//60000}:{position//1000%60:02} / {length//60000}:{length//1000%60:02}")
                if self.playing and length and position >= length - 100:
                    self.playing = False
                    self.button.configure(text="▶ Preview")
            except RuntimeError:
                return
            self.timer = self.after(500, self.tick)

    def pause(self):
        if self.player and self.player.path:
            self.player.pause()
        self.playing = False
        self.button.configure(text="▶ Preview")

    def seek(self):
        self.dragging = False
        if self.player and self.player.path:
            self.player.seek(self.seekbar.get())

    def cleanup(self, event):
        if event.widget is self:
            if self.timer:
                self.after_cancel(self.timer)
            if self.player:
                try:
                    self.player.close()
                except RuntimeError:
                    pass
            if self.load_timer:
                self.after_cancel(self.load_timer)
            if self.loading:
                def dispose(future):
                    try:
                        _, temporary = future.result()
                        if temporary:
                            temporary.cleanup()
                    except Exception:
                        pass
                self.loading.add_done_callback(dispose)
            self.loader.shutdown(wait=False, cancel_futures=True)
            if self.temporary:
                self.temporary.cleanup()
