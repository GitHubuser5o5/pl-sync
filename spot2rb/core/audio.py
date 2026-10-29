"""Local Windows audio preview. Codec support follows installed Windows drivers."""
import ctypes
from pathlib import Path
import uuid
import shutil
import subprocess
import tempfile


def prepare_audio(path):
    """Decode non-WAV formats to a disposable preview, never modify the original."""
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("Audio file no longer exists.")
    ffmpeg = shutil.which("ffmpeg")
    if path.suffix.lower() == ".wav" or not ffmpeg:
        return str(path), None
    temporary = tempfile.TemporaryDirectory(prefix="spot2rb-preview-")
    output = Path(temporary.name) / "preview.wav"
    try:
        process = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-i", str(path),
                                  "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(output)],
                                 capture_output=True, timeout=120,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if process.returncode:
            raise RuntimeError("Could not decode this file for preview.")
        return str(output), temporary
    except Exception:
        temporary.cleanup()
        raise


class AudioPreview:
    def __init__(self):
        self.api = ctypes.WinDLL("winmm")
        self.api.mciSendStringW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        self.api.mciGetErrorStringW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
        self.alias = "preview" + uuid.uuid4().hex
        self.path = None
        self.cue = 0

    def command(self, text):
        output = ctypes.create_unicode_buffer(1024)
        code = self.api.mciSendStringW(text, output, len(output), None)
        if code:
            self.api.mciGetErrorStringW(code, output, len(output))
            raise RuntimeError(output.value or "Windows cannot preview this audio format.")
        return output.value

    def load(self, path):
        path = str(Path(path).resolve())
        if path == self.path:
            return
        self.close()
        if not Path(path).is_file() or '"' in path:
            raise ValueError("Choose an existing local audio file.")
        self.command(f'open "{path}" alias {self.alias}')
        self.path = path
        self.cue = 0
        self.command(f"set {self.alias} time format milliseconds")

    def play(self):
        self.command(f"play {self.alias}")

    def pause(self):
        self.command(f"pause {self.alias}")

    def position(self):
        return int(self.command(f"status {self.alias} position"))

    def length(self):
        return int(self.command(f"status {self.alias} length"))

    def seek(self, milliseconds):
        playing = self.command(f"status {self.alias} mode") == "playing"
        self.command(f"seek {self.alias} to {max(0, min(int(milliseconds), self.length()))}")
        if playing:
            self.play()

    def close(self):
        if self.path:
            try:
                self.command(f"close {self.alias}")
            finally:
                self.path = None
