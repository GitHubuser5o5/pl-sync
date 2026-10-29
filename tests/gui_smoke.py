"""Explicit desktop check: python tests/gui_smoke.py (temporary data only)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tempfile
import time
import wave
import subprocess
import shutil
from unittest.mock import patch
from types import SimpleNamespace

import spot2rb.ui.main as ui
from spot2rb.ui.export import ExportWindow
from spot2rb.core.audio import AudioPreview, prepare_audio
from spot2rb.core.rbimport import read_collection


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    (root / "config.toml").write_text((ui.BASE / "config.toml").read_text())
    ui.BASE = root
    audio = root / "silence.wav"
    with wave.open(str(audio), "wb") as stream:
        stream.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\0\0" * 24000)
    xml = root / "collection.xml"
    xml.write_text(f'<DJ_PLAYLISTS><COLLECTION><TRACK TrackID="1" Name="Song" Artist="Artist" TotalTime="3" Location="{audio.as_uri()}"/></COLLECTION><PLAYLISTS><NODE Name="ROOT" Type="0"><NODE Name="A" Type="1" KeyType="0"/><NODE Name="B" Type="1" KeyType="0"/></NODE></PLAYLISTS></DJ_PLAYLISTS>')
    def pump(done, seconds=10):
        deadline = time.monotonic() + seconds
        while not done() and time.monotonic() < deadline:
            app.update()
            time.sleep(.02)
    app = ui.App(autoload=False)
    app.withdraw()
    app.collection = read_collection(xml)
    track = {"spotify_id": "track1", "title": "Song", "artists": ["Artist"], "duration_ms": 3000, "album": "", "year": "", "isrc": ""}
    ready = {"playlist_id": "ready", "name": "Ready", "tracks": [track], "skipped": []}
    missing = {"playlist_id": "missing", "name": "Missing", "tracks": [dict(track, title="Absent", spotify_id="track2")], "skipped": []}
    app.fetched = [ready, missing]
    app.playlists = [{"id": "missing", "name": "Missing"}, {"id": "ready", "name": "Ready"}]
    app.show_tracks()
    from unittest.mock import Mock
    app.set_playlists([dict(p, snapshot_id="s1") for p in app.playlists])
    app.search.set("rea")
    assert app.playlist_table.iids() == ("1",)
    app.playlist_table.select(["1"])
    assert app.selected_playlist_index() == 1
    app.search.set("zzz")
    assert app.playlist_table.iids() == ()
    app.search.set("")
    assert app.playlist_table.iids() == ("0", "1")
    assert app.marker(app.playlists[1]) == ""
    app.mark_exported("ready")
    assert app.marker(app.playlists[1])[2] == "Exported"
    app.playlists[1]["snapshot_id"] = "s2"  # edited in Spotify after the export
    assert app.marker(app.playlists[1])[2] == "Changed"
    app.mark_exported("ready")  # exported again
    assert app.marker(app.playlists[1])[2] == "Exported"
    app.exported.clear()
    app.playlist_table.select(["1"])
    app.spotify = SimpleNamespace(token={}, tracks=Mock(return_value=ready))
    with patch("spot2rb.ui.import_dialog.ImportDialog") as destination:
        app.prepare_playlist(True)
        deadline = time.monotonic() + 5
        while app.busy and time.monotonic() < deadline:
            app.update()
            time.sleep(.02)
        app.spotify.tracks.assert_called_once_with("ready")
        destination.assert_called_once_with(app, ready, True)
    app.spotify.tracks.reset_mock()
    with patch("spot2rb.ui.import_dialog.ImportDialog") as destination:
        app.prepare_playlist(False)
        deadline = time.monotonic() + 5
        while app.busy and time.monotonic() < deadline:
            app.update()
            time.sleep(.02)
        app.spotify.tracks.assert_called_once_with("ready")
        destination.assert_called_once_with(app, ready, False)
    review = ExportWindow(app, ready)
    review.withdraw()
    app.update()
    assert review.rows[0]["confidence"] == 4
    assert review.options.selection() == ("0",)
    assert review.preview.button.cget("text") == "▶ Preview"
    review.preview.toggle()
    deadline = time.monotonic() + 5
    while review.preview.loading and time.monotonic() < deadline:
        app.update()
        time.sleep(.02)
    assert review.preview.player.path
    assert review.preview.button.cget("text") == "Pause"
    review.preview.toggle()
    assert review.preview.button.cget("text") == "▶ Preview"
    review.only_attention.set(True)
    review.refresh()
    assert not review.table.iids()
    review.destroy()
    from spot2rb.ui.import_dialog import ImportDialog
    assert app.tabs.names == ["Playlists", "Queue", "Connect"]
    assert app.playlist_table.iids() == ("0", "1")
    with patch("spot2rb.ui.dialogs.ask_choice", side_effect=lambda t, m, b, **k: len(b) - 1):
        dialog = ImportDialog(app, ready, True)
        dialog.continue_action()
        pump(lambda: len(app.sync_queue) == 1)
        assert len(app.sync_queue) == 1
        assert app.sync_queue[0]["mode"] == "new"
        dialog = ImportDialog(app, ready, True)
        dialog.continue_action()
        pump(lambda: len(app.sync_queue) == 2)
        assert len(app.sync_queue) == 2
    app.queue_screen.refresh()
    (root / "out").mkdir()
    app.output_dir.set(str(root / "out"))
    app.queue_screen.start()
    deadline = time.monotonic() + 10
    while app.queue_screen.running and time.monotonic() < deadline:
        app.update()
        time.sleep(.02)
    assert all(q["status"] == "Exported — import into Rekordbox" for q in app.sync_queue), app.sync_queue
    assert Path(app.sync_queue[0]["output"]).suffix == ".m3u8"
    assert sorted(p.name for p in (root / "out").iterdir()) == ["Ready-2.m3u8", "Ready.m3u8"]
    # Attention happens before admission, and cancellation adds no task.
    dialog = ImportDialog(app, missing, True)
    dialog.continue_action()
    pump(lambda: any(isinstance(w, ExportWindow) for w in app.winfo_children()))
    popup = next(w for w in app.winfo_children() if isinstance(w, ExportWindow))
    assert len(app.sync_queue) == 2
    popup.destroy()
    dialog.destroy()
    # Auto button resolves everything: no candidate -> skipped, then the callback runs.
    got = []
    auto = ExportWindow(app, missing, attention_only=True, on_ready=got.append)
    with patch("spot2rb.ui.dialogs.ask_choice", return_value=0) as ask:
        auto.continue_action()  # "Go back": nothing happens
        assert ask.called and not got
    with patch("spot2rb.ui.dialogs.ask_choice", return_value=1):
        auto.continue_action()  # "Auto": resolves and continues
    assert got and got[0][0]["status"] == "skipped" and got[0][0]["path"] is None
    app.xml.set(str(xml))
    app.spotify = SimpleNamespace(token={}, playlists=lambda: app.playlists[:], tracks=lambda pid: ready if pid == "ready" else missing)
    app.refresh_on_launch()
    deadline = time.monotonic() + 10
    while app.busy and time.monotonic() < deadline:
        app.update()
        time.sleep(.02)
    assert "Startup refresh finished" in app.status.get(), app.status.get()
    app.pairings = {"ready": {"destination": ["ROOT", "B"], "remove_extra": False}}
    assert app.persist()
    app.destroy()
    app = ui.App(autoload=False)
    app.withdraw()
    assert app.pairings["ready"]["destination"] == ["ROOT", "B"]
    assert len(app.sync_queue) == 2
    assert app.output_dir.get() == str(root / "out")
    app.queue_screen.refresh()
    app.queue_screen.table.select([app.sync_queue[0]["id"]])
    app.queue_screen.remove_selected()
    assert len(app.sync_queue) == 1
    with patch("spot2rb.ui.dialogs.askyesno", return_value=True):
        app.queue_screen.clear()
    assert app.sync_queue == []
    app.destroy()
    player = AudioPreview()
    try:
        player.load(audio)
        assert player.length() == 3000
        player.play()
        player.pause()
        player.seek(1000)
        assert 950 <= player.position() <= 1050
        player.cue = 500
        player.seek(player.cue)
        assert 450 <= player.position() <= 550
    finally:
        player.close()
    if shutil.which("ffmpeg"):
        flac = root / "silence.flac"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(audio), str(flac)], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        decoded, scratch = prepare_audio(flac)
        try:
            player.load(decoded)
            assert player.length() == 3000
        finally:
            player.close()
            scratch.cleanup()
print("Redesigned tabs, name popup, pre-queue review, M3U8-only queue exports, queue delete/clear, startup refresh and audio checks passed.")
