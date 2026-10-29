from pathlib import Path
import tempfile
import unittest
from spot2rb.core import state
from spot2rb.core.matcher import match, candidates, match_rekordbox
from spot2rb.core.m3u import write_playlist
from spot2rb.core.review import build_rows, needs_attention


class ExportTests(unittest.TestCase):
    def test_rekordbox_only_with_folder_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            rb_file = Path(directory) / "registered.mp3"
            local_file = Path(directory) / "folder.flac"
            rb_file.touch()
            local_file.touch()
            track = {"title": "Song", "artists": ["Artist"], "duration_ms": 120000}
            library = {"tracks": [dict(track, path=str(local_file)), dict(track, path=str(rb_file))]}
            collection = {"tracks": {"1": {"path": str(rb_file), "attributes": {"Name": "Song", "Artist": "Artist", "TotalTime": "120"}}}}
            files = candidates(library, collection)
            self.assertEqual(match_rekordbox(track, files)["path"], str(rb_file))
            # A remembered choice from the old folder-based workflow cannot bypass the restriction.
            self.assertEqual(match_rekordbox(track, files, {"id": str(local_file)}, "id")["path"], str(rb_file))
            files = candidates(library, {"tracks": {}})
            result = match_rekordbox(track, files, {"id": str(local_file)}, "id")
            self.assertIsNone(result["path"])
            self.assertIn("not imported into Rekordbox", result["status"])
            self.assertTrue(result["diagnostics"])
            self.assertEqual(result["candidates"], [])
            self.assertEqual(match_rekordbox(track, [], {}, "id")["status"], "unmatched")

    def test_same_file_is_used_once_per_playlist(self):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "Midt i en dr\u00f8m.mp3"
            audio.touch()
            collection = {"tracks": {"1": {"path": str(audio), "attributes": {"Name": "Midt i en dr\u00f8m", "Artist": "One Two", "TotalTime": "269"}}}}
            library = {"tracks": []}
            def spotify(position, ms):
                return {"position": position, "spotify_id": f"s{position}", "title": "Midt i en dr\u00f8m", "artists": ["One Two"], "duration_ms": ms}
            playlist = {"tracks": [spotify(1, 270000), spotify(2, 269000)], "skipped": []}
            rows = build_rows(playlist, library, collection, {})
            self.assertEqual([bool(r["path"]) for r in rows], [False, True])
            self.assertEqual(rows[0]["status"], "duplicate")
            self.assertFalse(needs_attention(rows[0]))
            output = Path(directory) / "p.m3u8"
            self.assertEqual(write_playlist(output, rows), (1, 1))

    def test_session_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            saved = {"folder": "C:/Müsic", "fetched": [{"name": "Set"}], "answers": {"id": None}}
            state.save(path, saved)
            self.assertEqual(state.load(path), saved)
            state.save(path, {"folder": "new"})
            self.assertEqual(state.load(path), {"folder": "new"})

    def test_duplicate_and_version_review(self):
        track = {"title": "Song", "artists": ["Artist"], "isrc": "123", "duration_ms": 120000}
        original = dict(track, path="a.mp3")
        remix = dict(track, title="Song (Remix)", path="b.mp3")
        self.assertEqual(match(track, [original])["status"], "matched")
        self.assertEqual(match(track, [original, dict(original, path="b.mp3")])["status"], "suggested")
        self.assertEqual(match(track, [remix])["path"], "b.mp3")
        self.assertEqual(match(track, [dict(original, duration_ms=200000)])["status"], "suggested")

    def test_preselection_prefers_identity_then_quality(self):
        track = {"title": "Song", "artists": ["Artist"], "isrc": "123", "duration_ms": 120000}
        low = dict(track, path="low.mp3", bitrate=128000)
        high = dict(track, path="high.mp3", bitrate=320000)
        lossless = dict(track, path="lossless.flac")
        remix = dict(track, title="Song (Remix)", path="remix.flac")
        wrong_artist = dict(track, artists=["Other"], isrc="", path="wrong.flac")
        self.assertEqual(match(track, [low, high])["path"], "high.mp3")
        self.assertEqual(match(track, [lossless, high])["path"], "lossless.flac")
        self.assertEqual(match(track, [remix, wrong_artist, low])["path"], "low.mp3")
        self.assertEqual(match(track, [high, low]), match(track, [low, high]))
        self.assertIsNone(match(track, [dict(low, title="Unrelated", artists=["Other"], isrc="")])["path"])

    def test_unicode_order_duplicates_backup_and_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "Beyoncé #1.wav"
            audio.write_bytes(b"audio")
            track = {"title": "Song", "artists": ["Artist"], "duration_ms": 120000}
            row = {"track": track, "path": str(audio), "status": "matched"}
            missing = {"track": track, "path": None, "status": "unmatched"}
            output = root / "set.m3u8"
            self.assertEqual(write_playlist(output, [row, missing, row]), (1, 2))
            self.assertFalse(output.with_suffix(".unmatched.csv").exists())
            write_playlist(output, [row, missing, row], write_report=True)
            self.assertEqual(output.read_text(encoding="utf-8").splitlines()[2::2], [str(audio)])
            self.assertIn("unmatched", output.with_suffix(".unmatched.csv").read_text(encoding="utf-8-sig"))
            write_playlist(output, [row])
            self.assertEqual(len(list(root.glob("set.m3u8.*.bak"))), 2)
            audio.unlink()
            with self.assertRaises(ValueError):
                write_playlist(output, [row])


if __name__ == "__main__":
    unittest.main()
