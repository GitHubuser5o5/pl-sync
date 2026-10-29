"""Rank plausible local matches and preselect the best for optional review."""
from pathlib import Path
import re
import unicodedata


def normalize(value):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return " ".join(re.sub(r"[^\w]+", " ", value).split())


def path_key(path):
    return str(Path(path).resolve()).casefold()


def candidates(library, collection):
    by_path = {}
    for item in (collection or {}).get("tracks", {}).values():
        attrs = item["attributes"]
        if not item.get("path"):
            continue
        track = {"path": item["path"], "title": attrs.get("Name", ""),
                 "artists": [attrs.get("Artist", "")], "isrc": attrs.get("ISRC", ""),
                 "duration_ms": float(attrs.get("TotalTime") or 0) * 1000,
                 "format": attrs.get("Kind", ""), "bitrate": float(attrs.get("BitRate") or 0) * 1000,
                 "in_rekordbox": True}
        by_path[str(Path(track["path"]).resolve()).casefold()] = track
    for track in (library or {}).get("tracks", []):
        key = str(Path(track["path"]).resolve()).casefold()
        if key in by_path:
            previous = by_path[key]
            by_path[key] = {**track, **{k: v for k, v in previous.items() if v}}
        else:
            by_path[key] = dict(track, in_rekordbox=False)
    return [t for t in by_path.values() if Path(t["path"]).is_file()]


def match_rekordbox(track, files, answers=None, key=None):
    registered = [item for item in files if item.get("in_rekordbox")]
    result = match(track, registered)
    result["diagnostics"] = []
    if not result["path"]:
        local = match(track, [item for item in files if not item.get("in_rekordbox")])
        result["diagnostics"] = local["candidates"]
        if local["path"]:
            result["status"] = ("File found, but not imported into Rekordbox"
                                if local["status"] == "matched" else
                                "Possible file found, but not imported into Rekordbox")
    if answers is not None and key in answers:
        saved = answers[key]
        if saved is None:
            result.update(status="skipped", path=None)
        elif path_key(saved) in {path_key(item["path"]) for item in registered}:
            result.update(status="chosen", path=saved)
    return result


def match(track, files):
    title = normalize(track["title"])
    artists = {normalize(a) for a in track.get("artists", []) if a}
    isrc = normalize(track.get("isrc"))
    exact, uncertain = [], []
    for item in files:
        same_title = title and title == normalize(item.get("title"))
        same_artist = bool(artists & {normalize(a) for a in item.get("artists", []) if a})
        same_isrc = isrc and isrc == normalize(item.get("isrc"))
        duration = track.get("duration_ms")
        local_duration = item.get("duration_ms")
        duration_ok = not duration or not local_duration or abs(duration - local_duration) <= 3000
        if (same_isrc or (same_title and same_artist)) and same_title and duration_ok:
            exact.append(item)
        elif same_isrc or same_title or normalize(Path(item["path"]).stem) == normalize(" - ".join([", ".join(track.get("artists", [])), track["title"]])):
            uncertain.append(item)
    def rank(item):
        duration, local_duration = track.get("duration_ms"), item.get("duration_ms")
        difference = abs(duration - local_duration) if duration and local_duration else float("inf")
        lossless = Path(item["path"]).suffix.casefold() in {".flac", ".wav", ".aif", ".aiff"}
        return (
            title == normalize(item.get("title")),
            bool(artists & {normalize(a) for a in item.get("artists", []) if a}),
            bool(isrc and isrc == normalize(item.get("isrc"))),
            difference <= 3000,
            -int(difference // 1000) if difference != float("inf") else float("-inf"),
            lossless, item.get("bitrate") or 0,
        )
    # Stable path tie-break makes the choice independent of scan order.
    def ordered(items):
        return sorted(sorted(items, key=lambda item: item["path"].casefold()), key=rank, reverse=True)
    options = ordered(exact) + ordered(uncertain)
    if not options:
        return {"status": "unmatched", "path": None, "candidates": []}
    confident = len(exact) == 1 and not uncertain
    return {"status": "matched" if confident else "suggested", "path": options[0]["path"], "candidates": options}
