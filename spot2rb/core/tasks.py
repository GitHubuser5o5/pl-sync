"""Execute already-reviewed playlist tasks; never fetch or rematch in the queue."""
from pathlib import Path
import hashlib
from .matcher import path_key
from .m3u import write_playlist
from .sync import plan, stage_xml


def validate_task(task, collection):
    if task.get("schema") != 2:
        raise ValueError("Old queue task: add this playlist again from Playlists to review it first.")
    if task["source_hash"] != collection.get("sha256"):
        raise ValueError("Collection changed. Add this task again from Playlists.")
    if hashlib.sha256(Path(collection["source"]).read_bytes()).hexdigest() != task["source_hash"]:
        raise ValueError("Source XML changed. Rescan and add this playlist again.")
    registered = {path_key(t["path"]) for t in collection["tracks"].values() if t.get("path")}
    for row in task["rows"]:
        if row.get("path") and (path_key(row["path"]) not in registered or not Path(row["path"]).is_file()):
            raise ValueError("A reviewed file is missing or no longer in Rekordbox. Review this playlist again.")


def execute(task, collection, output, working_collection=None):
    validate_task(task, collection)
    if task["mode"] == "new":
        write_playlist(output, task["rows"])
        return None
    current = working_collection or collection
    changes = plan(current, task["destination"], task["rows"], False)
    stage_xml(current["source"], output, changes, current["sha256"])
    return changes
