"""Songs from a Spotify playlist for which no downloaded file was found (to download them yourself)."""
from pathlib import Path


def missing_rows(rows):
    """Rows with no file: not matched, not skipped-by-duplicate, and not 'file exists but is not in Rekordbox'."""
    return [row for row in rows
            if not row.get("path") and row.get("status") != "duplicate" and not str(row.get("status", "")).startswith("File found")]


def label(row):
    track = row["track"]
    artists = ", ".join(track.get("artists", []))
    text = f"{artists} - {track['title']}" if artists else track["title"]
    return text.replace("\r", " ").replace("\n", " ")


def missing_text(rows):
    seen, lines = set(), []
    for row in missing_rows(rows):
        line = label(row)
        if line.casefold() not in seen:
            seen.add(line.casefold())
            lines.append(line)
    return "\n".join(lines) + ("\n" if lines else "")


def write_missing(path, rows):
    """Write one 'Artist - Title' per line (UTF-8); returns the number of songs written."""
    text = missing_text(rows)
    Path(path).write_text(text, encoding="utf-8")
    return text.count("\n")
