import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import wave

from spot2rb.core.library import scan
from spot2rb.core.rbimport import location_path, read_collection
from spot2rb.core.spotify import Spotify


class MissingTests(unittest.TestCase):
    def test_lists_only_songs_without_any_file(self):
        from spot2rb.core.missing import missing_rows, missing_text, write_missing
        def row(title, status, path=None, artists=("A",)):
            return {"track": {"title": title, "artists": list(artists)}, "status": status, "path": path}
        rows = [row("Have", "matched", "x.mp3"), row("Gone", "unmatched"), row("Skipped one", "skipped"), row("Dup", "duplicate"),
                row("In folder only", "File found, but not imported into Rekordbox"), row("Gone", "unmatched")]
        self.assertEqual([r["track"]["title"] for r in missing_rows(rows)], ["Gone", "Skipped one", "Gone"])
        self.assertEqual(missing_text(rows), "A - Gone\nA - Skipped one\n")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "m.txt"
            self.assertEqual(write_missing(path, rows), 2)
            self.assertEqual(path.read_text(encoding="utf-8"), "A - Gone\nA - Skipped one\n")
        self.assertEqual(missing_text([row("Have", "matched", "x.mp3")]), "")


class CoreTests(unittest.TestCase):
    def test_location_decodes_once(self):
        self.assertEqual(location_path("file://localhost/C:/Music/A%20%2520.mp3"), "C:/Music/A %20.mp3")
        self.assertEqual(location_path("file://server/share/A.mp3"), "//server/share/A.mp3")

    def test_nested_xml_and_missing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "collection.xml"
            path.write_text('<DJ_PLAYLISTS><COLLECTION><TRACK TrackID="1" Name="Mix" Location="file://localhost/C:/missing.mp3"/></COLLECTION><PLAYLISTS><NODE Name="ROOT" Type="0"><NODE Name="Set" Type="1" KeyType="0"><TRACK Key="1"/></NODE></NODE></PLAYLISTS></DJ_PLAYLISTS>')
            result = read_collection(path)
            self.assertEqual(result["playlists"][0]["path"], ["ROOT", "Set"])
            self.assertEqual(result["playlists"][0]["keys"], ["1"])
            self.assertFalse(result["tracks"]["1"]["exists"])

    def test_cache_and_deleted_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audio = root / "test.wav"
            with wave.open(str(audio), "wb") as stream:
                stream.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                stream.writeframes(b"\0\0" * 8000)
            first = scan(root, root / "cache.db")
            self.assertEqual(first["tracks"][0]["duration_ms"], 1000)
            with patch("spot2rb.core.library.read_audio", side_effect=AssertionError("Cache missed")):
                self.assertEqual(scan(root, root / "cache.db")["tracks"], first["tracks"])
            audio.unlink()
            self.assertEqual(scan(root, root / "cache.db")["tracks"], [])

    def test_scan_subfolder_options(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder in ("", "keep", "unsorted"):
                (root / folder).mkdir(exist_ok=True)
                with wave.open(str(root / folder / "t.wav"), "wb") as stream:
                    stream.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                    stream.writeframes(b"\0\0" * 800)
            def found(**options):
                return sorted(Path(t["path"]).parent.name for t in scan(root, root / "cache.db", **options)["tracks"])
            self.assertEqual(found(), [root.name])
            self.assertEqual(found(subfolders=True), sorted([root.name, "keep", "unsorted"]))
            self.assertEqual(found(subfolders=True, include=["keep"]), sorted([root.name, "keep"]))
            self.assertEqual(found(subfolders=True, include=[]), [root.name])

    def test_pagination_duplicates_and_unavailable(self):
        client = Spotify("test")
        track = {"type": "track", "id": "a", "name": "Song", "artists": [{"name": "Artist"}]}
        with patch.object(client, "get", side_effect=[
            {"items": [{"item": track}, {"item": None}], "next": "https://api.spotify.com/v1/next"},
            {"items": [{"track": track}], "next": None},
        ]) as get:
            result = client.tracks("playlist")
        self.assertEqual(get.call_count, 2)
        self.assertEqual([t["position"] for t in result["tracks"]], [1, 3])
        self.assertEqual(len(result["skipped"]), 1)
        self.assertIsNone(result["tracks"][0]["isrc"])

    def test_token_never_sent_to_other_host(self):
        with self.assertRaisesRegex(RuntimeError, "Unexpected"):
            Spotify("test").get("https://example.com/page")


if __name__ == "__main__":
    unittest.main()
