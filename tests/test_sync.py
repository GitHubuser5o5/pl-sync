from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET

from spot2rb.core.rbimport import read_collection
from spot2rb.core.review import confidence, needs_attention, build_rows
from spot2rb.core.sync import plan, stage_xml


class SyncTests(unittest.TestCase):
    def test_confidence_and_manual_resolution(self):
        track = {"title": "Song", "artists": ["Artist"], "isrc": "ABC", "duration_ms": 100000}
        self.assertEqual(confidence(track, track), 5)
        self.assertEqual(confidence(track, dict(track, isrc="")), 4)
        self.assertEqual(confidence(track, dict(track, duration_ms=None)), 3)
        self.assertEqual(confidence(track, dict(track, artists=["Other"], isrc="")), 2)
        self.assertEqual(confidence(track, None), 0)
        row = {"status": "suggested", "path": "file", "confidence": 5, "candidates": [{}, {}]}
        self.assertTrue(needs_attention(row))
        self.assertFalse(needs_attention(dict(row, status="chosen")))
        self.assertFalse(needs_attention(dict(row, status="skipped", path=None)))

    def fixture(self, root):
        for name in ("a", "b", "c"):
            (root / (name + ".wav")).touch()
        source = root / "source.xml"
        source.write_text('<DJ_PLAYLISTS Version="1.0.0"><COLLECTION Entries="3">' + ''.join(
            f'<TRACK TrackID="{i}" Name="{name}" Artist="Artist" Location="{(root / (name + ".wav")).as_uri()}"><POSITION_MARK Name="Cue" Start="4"/></TRACK>'
            for i, name in enumerate(("a", "b", "c"), 1)) +
            '</COLLECTION><PLAYLISTS><NODE Name="ROOT" Type="0"><NODE Name="Set" Type="1" KeyType="0" Entries="2"><TRACK Key="1"/><TRACK Key="2"/></NODE><NODE Name="Other" Type="1" KeyType="0" Entries="1"><TRACK Key="3"/></NODE></NODE></PLAYLISTS></DJ_PLAYLISTS>', encoding="utf-8")
        return source, read_collection(source)

    def test_add_only_and_remove_preserve_collection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, collection = self.fixture(root)
            original = source.read_bytes()
            rows = [{"path": str(root / "b.wav")}, {"path": str(root / "c.wav")}, {"path": None}]
            add = plan(collection, ["ROOT", "Set"], rows)
            self.assertEqual((add["add"], add["remove"], add["after"]), (1, 0, ["1", "2", "3"]))
            remove = plan(collection, ["ROOT", "Set"], rows, True)
            self.assertEqual((remove["add"], remove["remove"], remove["after"]), (1, 1, ["2", "3"]))
            output = root / "prepared.xml"
            stage_xml(source, output, remove, collection["sha256"])
            result = read_collection(output)
            self.assertEqual(result["playlists"][0]["keys"], ["2", "3"])
            self.assertEqual(result["playlists"][1]["keys"], ["3"])
            self.assertEqual(len(ET.parse(output).findall("./COLLECTION/TRACK/POSITION_MARK")), 3)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(len(result["tracks"]), 3)
            self.assertTrue((root / "a.wav").exists())
            stage_xml(source, output, remove, collection["sha256"])
            self.assertEqual(len(list(root.glob("prepared.xml.*.bak"))), 1)
            with self.assertRaises(ValueError):
                stage_xml(source, source, remove, collection["sha256"])
            source.write_bytes(original + b"\n")
            with self.assertRaisesRegex(ValueError, "changed"):
                stage_xml(source, output, remove, collection["sha256"])

    def test_duplicates_and_unknown_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, collection = self.fixture(root)
            rows = [{"path": str(root / "b.wav")}] * 2
            result = plan(collection, ["ROOT", "Set"], rows)
            self.assertEqual(result["after"], ["1", "2", "2"])
            with self.assertRaises(ValueError):
                plan(collection, ["Unknown"], rows)
            with self.assertRaises(ValueError):
                plan(collection, ["ROOT", "Set"], [{"path": str(root / "missing.wav")}])


if __name__ == "__main__":
    unittest.main()
