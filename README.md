<p align="center">
  <img src="spot2rb/assets/logo_256.png" alt="PL-SYNC" width="160">
</p>

# PL-SYNC

PL-SYNC matches the tracks in your Spotify playlists against the files in your Rekordbox collection and exports the result as an M3U8 playlist that Rekordbox can import. Spotify provides the track list and order; your local files provide the audio and tags. Your collection is never modified.

The Python package is called `spot2rb`. Windows only.

## Contents

- [Installation](#installation)
- [Setup](#setup)
- [Usage](#usage)
- [How matching works](#how-matching-works)
- [Limitations](#limitations)
- [Development](#development)
- [Project layout](#project-layout)
- [Disclaimer](#disclaimer)

## Installation

Requirements:

- Windows
- Python 3.11 or newer, with Tkinter
- FFmpeg on your `PATH` (optional, improves audio preview)

```powershell
git clone https://github.com/GitHubuser5o5/pl-sync.git
cd pl-sync
python -m pip install -r requirements.txt
python -m spot2rb.app
```

`start.bat` starts the app without a console window and uses `.venv` in the project folder if one exists. Crashes are written to `spot2rb/data/app.log`.

## Setup

1. Create an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and add `http://127.0.0.1:8888/callback` as a redirect URI. Only the Client ID is needed; there is no client secret.
2. Open the **Connect** tab, paste the Client ID and log in.
3. In Rekordbox, export your collection as XML and select that file in Connect. Export it again whenever your collection changes.
4. Select a **Download folder**. Exported playlists are saved there.
5. Optional: select a music folder to detect files that are on disk but not yet in Rekordbox. Tick **Also search subfolders** to include subfolders, use **Choose subfolders** to pick which ones, then press **Scan local library**. Files found only in this folder are never exported.

Settings are remembered. On launch the app rescans the saved folder and XML and refreshes your playlist list.

## Usage

### Export a playlist

1. Open the **Playlists** tab. Type in the search box to filter by name.
2. Select a playlist and choose **Export** or **Add to queue**. The latest tracks are fetched automatically. **Preview playlist** shows the track list first.
3. Enter a name for the playlist.
4. If any tracks need a decision, the **Needs attention** dialog opens. For each track, accept a candidate, choose another file from the collection, or skip it. **Auto** accepts the best-ranked file for every open track and skips tracks with no candidate. Earlier manual choices are remembered.

The **Marker** column shows `Queued`, `Exported` or `Changed`. `Changed` means the playlist was edited in Spotify after your last export.

### Queue

The **Queue** tab lists the tasks you added. **Start queue** writes them all to the download folder. Select tasks and press Delete to remove them, or press **Clear** to empty the list. Tasks use their already reviewed matches, so nothing is fetched or matched again while the queue runs. A failed task is shown in the list and the rest continue. Existing output files are backed up before being replaced, and duplicate names get a numbered suffix.

### Import into Rekordbox

In Rekordbox, choose **File > Import > Import Playlist** and select the exported `.m3u8` file.

## How matching works

Each Spotify track is compared with the Rekordbox collection by title, artist and duration first. Among otherwise equal files, lossless audio and higher bitrates are preferred.

Five boxes show confidence: 1-2 low, 3 possible, 4 strong, 5 very strong. These are heuristic levels, not probabilities. Low confidence, several candidates, missing tracks and folder-only files all open the review dialog.

A file is used once per playlist. If several Spotify entries match the same file (for example the same song on two albums), the closest fit keeps it and the others are marked as duplicates and left out.

Select a candidate and press **Preview** to listen to it, with a slider to seek. Playback is handled by Windows. When FFmpeg is available, non-WAV files are decoded to temporary WAV files in the background.

## Limitations

- Rekordbox cannot be updated while it is running. PL-SYNC only writes files; it does not create or change playlists inside Rekordbox. Adding songs to an existing playlist is a manual step.
- Spotify apps in development mode require the app owner to have Premium and only expose the contents of playlists you own or collaborate on. Other playlists are hidden because their tracks cannot be fetched. See Spotify's [migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide).
- Artist genres are not fetched.
- Tracks that are not in the Rekordbox collection XML are excluded from the export. No report file is written.

## Development

Local data (settings, Spotify login, playlists, scan results, queue) is stored in `spot2rb/data/` and is excluded from git. The login is encrypted with Windows DPAPI, so it can only be read by your Windows account.

Run the tests:

```powershell
python -m unittest discover -s tests -v
python tests/gui_smoke.py
```

`gui_smoke.py` drives the interface with temporary data and silent audio. A live Spotify login and a real Rekordbox import are not covered and need your own account.

## Project layout

```
spot2rb/
  app.py        entry point
  config.toml   defaults (empty Client ID)
  core/         Spotify client, matcher, library scan, M3U8 export, queue, state
  ui/           Tkinter interface and dialogs
  assets/       logo and icons
  data/         local app data (git-ignored)
tests/          unit tests and GUI smoke test
start.bat       windowless launcher
```

## Disclaimer

Not affiliated with or endorsed by Spotify or AlphaTheta / Pioneer DJ. Spotify and Rekordbox are trademarks of their respective owners.
