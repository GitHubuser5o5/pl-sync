"""Read collection metadata and nested playlists without modifying source XML."""
import re
import hashlib
from pathlib import Path
from urllib.parse import unquote, urlsplit
from defusedxml import ElementTree


def location_path(location):
    uri = urlsplit(location)
    if uri.scheme != "file":
        raise ValueError(f"Expected a file URI: {location}")
    path = unquote(uri.path)
    if uri.netloc and uri.netloc.lower() != "localhost":
        return "//" + uri.netloc + path
    if re.match(r"^/[A-Za-z]:/", path):
        path = path[1:]
    return path


def read_collection(xml_path):
    root = ElementTree.parse(xml_path).getroot()
    if root.tag != "DJ_PLAYLISTS" or root.find("COLLECTION") is None:
        raise ValueError("This is not a Rekordbox collection XML.")
    tracks, warnings = {}, []
    for node in root.findall("./COLLECTION/TRACK"):
        attrs = dict(node.attrib)
        track_id = attrs.get("TrackID")
        if not track_id:
            warnings.append("Collection track has no TrackID")
            continue
        try:
            path = location_path(attrs.get("Location", ""))
        except ValueError as exc:
            warnings.append(str(exc))
            path = ""
        tracks[track_id] = {"rekordbox_id": track_id, "path": path,
                            "exists": bool(path) and Path(path).is_file(), "attributes": attrs}
    playlists = []
    def visit(node, parents):
        names = parents + [node.get("Name", "Unnamed")]
        if node.get("Type") == "1":
            key_type = node.get("KeyType", "0")
            keys = [track.get("Key", "") for track in node.findall("TRACK")]
            playlists.append({"path": names, "key_type": key_type, "keys": keys})
        for child in node.findall("NODE"):
            visit(child, names)
    for node in root.findall("./PLAYLISTS/NODE"):
        visit(node, [])
    return {"tracks": tracks, "playlists": playlists, "warnings": warnings,
            "source": str(Path(xml_path).resolve()), "sha256": hashlib.sha256(Path(xml_path).read_bytes()).hexdigest()}
