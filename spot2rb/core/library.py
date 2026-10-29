"""Read-only audio scan with an incremental SQLite metadata cache."""
import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import mutagen

EXTENSIONS = {".mp3", ".flac", ".wav", ".aif", ".aiff", ".m4a", ".mp4", ".ogg", ".opus", ".aac", ".wma"}


def read_audio(path):
    audio = mutagen.File(path, easy=True)
    if audio is None:
        raise ValueError("Unrecognized audio format")
    tags = audio.tags or {}
    def values(*keys):
        for key in keys:
            value = tags.get(key)
            if value:
                return [str(v) for v in (value if isinstance(value, (list, tuple)) else [value])]
        return []
    return {"path": str(path), "title": next(iter(values("title", "TIT2")), ""),
            "artists": values("artist", "TPE1"), "album": next(iter(values("album", "TALB")), ""),
            "isrc": next(iter(values("isrc", "TSRC")), ""),
            "duration_ms": round(audio.info.length * 1000),
            "bitrate": getattr(audio.info, "bitrate", None), "format": path.suffix.lstrip(".").upper()}


def scan(folder, cache_path, subfolders=False, include=None):
    """Scan only `folder` itself by default.

    subfolders=True also searches below it; `include` (names of direct subfolders) limits that
    to the chosen ones, None meaning all of them."""
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Choose an existing music folder.")
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tracks, errors = [], []
    with closing(sqlite3.connect(cache_path)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, mtime INTEGER, size INTEGER, metadata TEXT)")
        def walk_error(error):
            errors.append({"path": error.filename, "error": str(error)})
        for directory, dirs, files in os.walk(root, onerror=walk_error, followlinks=False):
            if Path(directory) == root:
                allowed = set(include) if include is not None else None
                dirs[:] = [d for d in dirs if subfolders and (allowed is None or d in allowed)]
            for filename in sorted(files):
                path = Path(directory) / filename
                if path.suffix.lower() not in EXTENSIONS:
                    continue
                try:
                    stat = path.stat()
                    row = db.execute("SELECT mtime,size,metadata FROM files WHERE path=?", (str(path),)).fetchone()
                    if row and row[:2] == (stat.st_mtime_ns, stat.st_size):
                        track = json.loads(row[2])
                    else:
                        track = read_audio(path)
                        db.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?)",
                                   (str(path), stat.st_mtime_ns, stat.st_size, json.dumps(track)))
                    tracks.append(track)
                except (OSError, ValueError, mutagen.MutagenError) as exc:
                    errors.append({"path": str(path), "error": str(exc)})
    return {"root": str(root), "tracks": tracks, "errors": errors}
