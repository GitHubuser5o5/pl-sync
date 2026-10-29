"""UTF-8 M3U8 export referencing existing local files (optional unmatched CSV report)."""
import csv
import os
from datetime import datetime
from pathlib import Path
import shutil


def write_playlist(path, rows, write_report=False):
    path = Path(path)
    lines = ["#EXTM3U"]
    unmatched, seen = [], set()
    for row in rows:
        track, location = row["track"], row.get("path")
        if not location:
            unmatched.append(row)
            continue
        audio = Path(location).resolve()
        if os.path.normcase(str(audio)) in seen:
            unmatched.append(dict(row, status="duplicate"))
            continue
        seen.add(os.path.normcase(str(audio)))
        if not audio.is_file():
            raise ValueError(f"File no longer exists. Review again: {audio}")
        if "\n" in str(audio) or "\r" in str(audio):
            raise ValueError("Audio paths cannot contain line breaks.")
        label = (", ".join(track.get("artists", [])) + " - " + track["title"]).replace("\n", " ").replace("\r", " ")
        seconds = round(track["duration_ms"] / 1000) if track.get("duration_ms") else -1
        lines.extend([f"#EXTINF:{seconds},{label}", str(audio)])
    if len(lines) == 1:
        raise ValueError("No matched files to export. Choose local files in the review first.")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report = path.with_suffix(".unmatched.csv")
    for destination in ((path, report) if write_report else (path,)):
        if destination.exists():
            shutil.copy2(destination, destination.with_name(destination.name + f".{stamp}.bak"))
    temporary = path.with_suffix(".m3u8.tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(path)
    if write_report:
        with report.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(["Position", "Title", "Artists", "Spotify ID", "Reason"])
            for row in unmatched:
                t = row["track"]
                writer.writerow([t.get("position", ""), t["title"], ", ".join(t.get("artists", [])), t.get("spotify_id", ""), row["status"]])
    return len(lines[1:]) // 2, len(unmatched)
