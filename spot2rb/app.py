"""Run with python -m spot2rb.app from the project directory (start.bat does this without a console window)."""
import sys
from pathlib import Path


def prepare_windowless():
    """pythonw has no console: send output and errors to a log file instead of losing them."""
    if sys.stdout is None or sys.stderr is None:
        log_dir = Path(__file__).resolve().parent / "data"
        log_dir.mkdir(exist_ok=True)
        log = open(log_dir / "app.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


def set_taskbar_identity():
    """Give the window its own taskbar identity so Windows shows our icon instead of Python's."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PLSync.PlaylistCompanion")
        except Exception:
            pass


if __name__ == "__main__":
    prepare_windowless()
    set_taskbar_identity()
    from spot2rb.ui.main import main
    main()
