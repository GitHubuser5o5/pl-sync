"""Plan playlist changes and stage XML. Never writes the live Rekordbox database."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import hashlib
import shutil
import xml.etree.ElementTree as ET
from defusedxml.ElementTree import parse
from .matcher import path_key


def plan(collection, destination, rows, remove_extra=False):
    matches = [p for p in collection["playlists"] if p["path"] == destination]
    if len(matches) != 1:
        raise ValueError("Destination playlist is missing or its folder/name is ambiguous. Rescan your XML.")
    playlist = matches[0]
    if playlist["key_type"] != "0":
        raise ValueError("Sync requires a playlist using Rekordbox TrackID keys.")
    by_path = {path_key(t["path"]): key for key, t in collection["tracks"].items() if t.get("path")}
    desired = []
    for row in rows:
        if row.get("path"):
            key = by_path.get(path_key(row["path"]))
            if key is None or not Path(row["path"]).is_file():
                raise ValueError("A selected track is no longer available in this collection. Rescan.")
            desired.append(key)
    current = playlist["keys"]
    remaining = Counter(current)
    additions = []
    for key in desired:
        if remaining[key]:
            remaining[key] -= 1
        else:
            additions.append(key)
    removals = list((Counter(current) - Counter(desired)).elements()) if remove_extra else []
    final = desired if remove_extra else current + additions
    return {"destination": destination, "before": current[:], "after": final,
            "add": len(additions), "remove": len(removals),
            "unmatched": sum(not row.get("path") for row in rows)}


def stage_xml(source, output, changes, expected_hash):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError("Choose a separate output XML; the original collection is never overwritten.")
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("Source XML changed since scanning. Rescan before preparing a sync.")
    tree = parse(source)
    found = []
    def walk(node, parents):
        names = parents + [node.get("Name", "Unnamed")]
        if names == changes["destination"] and node.get("Type") == "1":
            found.append(node)
        for child in node.findall("NODE"):
            walk(child, names)
    for node in tree.getroot().findall("./PLAYLISTS/NODE"):
        walk(node, [])
    if len(found) != 1:
        raise ValueError("Destination playlist could not be uniquely located.")
    node = found[0]
    if [t.get("Key", "") for t in node.findall("TRACK")] != changes["before"]:
        raise ValueError("Playlist contents changed. Prepare the comparison again.")
    for child in list(node):
        if child.tag == "TRACK":
            node.remove(child)
    for key in changes["after"]:
        ET.SubElement(node, "TRACK", Key=key)
    node.set("Entries", str(len(changes["after"])))
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        shutil.copy2(output, output.with_name(output.name + datetime.now().strftime(".%Y%m%d-%H%M%S-%f.bak")))
    temporary = output.with_suffix(".tmp")
    tree.write(temporary, encoding="utf-8", xml_declaration=True)
    temporary.replace(output)
