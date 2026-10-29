from .matcher import candidates, match_rekordbox, normalize, path_key


def confidence(track, item):
    if not item:
        return 0
    title = normalize(track.get("title")) == normalize(item.get("title"))
    artist = bool({normalize(a) for a in track.get("artists", [])} & {normalize(a) for a in item.get("artists", [])})
    duration = track.get("duration_ms") and item.get("duration_ms")
    close = duration and abs(track["duration_ms"] - item["duration_ms"]) <= 3000
    isrc = track.get("isrc") and normalize(track["isrc"]) == normalize(item.get("isrc"))
    if title and (artist or isrc) and close:
        return 5 if isrc else 4
    if title and (artist or isrc):
        return 3
    return 2 if title or isrc else 1


def needs_attention(row):
    return row["status"] not in {"chosen", "skipped", "duplicate"} and (
        not row.get("path") or row.get("confidence", 0) <= 2 or len(row["candidates"]) > 1)


def build_rows(playlist, library, collection, answers):
    files = candidates(library, collection)
    by_path = {path_key(item["path"]): item for item in files}
    rows = []
    for track in playlist["tracks"]:
        key = track.get("spotify_id") or repr((track["title"], track.get("artists")))
        result = match_rekordbox(track, files, answers, key)
        item = by_path.get(path_key(result["path"])) if result["path"] else None
        rows.append(dict(result, track=track, key=key, confidence=confidence(track, item)))
    return drop_duplicates(rows)


def drop_duplicates(rows):
    """One file may appear only once per playlist.

    When several Spotify entries (e.g. the same song on two albums) resolve to the same file,
    the entry that fits best keeps it (ties: the earliest) and the others are marked duplicate."""
    groups = {}
    for index, row in enumerate(rows):
        if row.get("path"):
            groups.setdefault(path_key(row["path"]), []).append(index)
    for indexes in groups.values():
        def fit(i):
            row = rows[i]
            item = next((c for c in row.get("candidates", []) if c["path"] == row["path"]), None)
            wanted, found = row["track"].get("duration_ms"), (item or {}).get("duration_ms")
            return -abs(wanted - found) if wanted and found else float("-inf")
        keep = max(indexes, key=lambda i: (rows[i].get("confidence", 0), fit(i), -i))
        for i in indexes:
            if i != keep:
                rows[i].update(duplicate_of=rows[i]["path"], path=None, status="duplicate", confidence=0)
    return rows
