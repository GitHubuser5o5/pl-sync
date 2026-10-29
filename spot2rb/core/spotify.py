"""Spotify PKCE authorization; tokens stay in memory for this session."""
import base64
import hashlib
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen


class SpotifyError(RuntimeError):
    pass


class Spotify:
    def __init__(self, client_id, redirect_uri="http://127.0.0.1:8888/callback"):
        if not client_id.strip():
            raise ValueError("Enter your Spotify app Client ID first.")
        self.client_id = client_id.strip()
        self.redirect_uri = redirect_uri
        self.token = {}
        self.expires = 0
        self.hidden = 0

    def _token_request(self, fields):
        fields["client_id"] = self.client_id
        req = Request("https://accounts.spotify.com/api/token",
                      data=urlencode(fields).encode())
        try:
            with urlopen(req, timeout=30) as response:
                token = json.load(response)
        except HTTPError as exc:
            raise SpotifyError(f"Spotify login failed ({exc.code}). Log in again and check your app settings.") from exc
        self.token.update(token)
        self.expires = time.monotonic() + token.get("expires_in", 3600) - 60

    def login(self, open_browser, timeout=180):
        uri = urlsplit(self.redirect_uri)
        if uri.scheme != "http" or uri.hostname != "127.0.0.1" or not uri.port or uri.query or uri.fragment:
            raise ValueError("Use an http://127.0.0.1:PORT/callback redirect URI.")
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        result = {}

        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                request_uri = urlsplit(self.path)
                query = parse_qs(request_uri.query)
                valid = request_uri.path == uri.path and secrets.compare_digest(query.get("state", [""])[0], state)
                self.send_response(200 if valid else 400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Return to Playlist Companion." if valid else b"Invalid callback.")
                if valid:
                    result.update(code=query.get("code", [None])[0], error=query.get("error", [None])[0])

        with HTTPServer(("127.0.0.1", uri.port), Callback) as server:
            server.timeout = 0.5
            open_browser("https://accounts.spotify.com/authorize?" + urlencode({
                "client_id": self.client_id, "response_type": "code", "redirect_uri": self.redirect_uri,
                "scope": "playlist-read-private playlist-read-collaborative", "state": state,
                "code_challenge_method": "S256", "code_challenge": challenge}))
            deadline = time.monotonic() + timeout
            while not result and time.monotonic() < deadline:
                server.handle_request()
        if not result.get("code"):
            raise SpotifyError("Login denied or timed out. Try again.")
        self._token_request({"grant_type": "authorization_code", "code": result["code"],
                             "redirect_uri": self.redirect_uri, "code_verifier": verifier})

    def get(self, path):
        url = path if path.startswith("https://") else "https://api.spotify.com/v1/" + path.lstrip("/")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "api.spotify.com":
            raise SpotifyError("Unexpected API pagination URL.")
        for attempt in range(3):
            if time.monotonic() >= self.expires:
                if not self.token.get("refresh_token"):
                    raise SpotifyError("Log in to Spotify first.")
                self._token_request({"grant_type": "refresh_token", "refresh_token": self.token["refresh_token"]})
            try:
                req = Request(url, headers={"Authorization": "Bearer " + self.token["access_token"]})
                with urlopen(req, timeout=30) as response:
                    return json.load(response)
            except HTTPError as exc:
                if exc.code == 401 and attempt < 2:
                    self.expires = 0
                    continue
                if exc.code == 429:
                    delay = int(exc.headers.get("Retry-After", "5"))
                    if delay <= 30 and attempt < 2:
                        time.sleep(max(0, delay))
                        continue
                    raise SpotifyError(f"Spotify rate limit reached. Retry in {delay} seconds.") from exc
                if exc.code == 403:
                    raise SpotifyError("Spotify denied access. Check Premium, app user access, and playlist ownership/collaboration.") from exc
                raise SpotifyError(f"Spotify request failed (HTTP {exc.code}).") from exc

    def pages(self, path):
        while path:
            page = self.get(path)
            yield from page.get("items", [])
            path = page.get("next")

    def playlists(self):
        """Playlists whose contents Spotify lets this app read (owned or collaborative)."""
        items = [p for p in self.pages("me/playlists?limit=50") if p]
        try:
            me = self.get("me").get("id")
        except SpotifyError:
            me = None
        if not me:
            self.hidden = 0
            return items
        keep = [p for p in items if (p.get("owner") or {}).get("id") == me or p.get("collaborative")]
        self.hidden = len(items) - len(keep)
        return keep

    def tracks(self, playlist_id, include_genres=False):
        tracks, skipped, genres = [], [], {}
        for index, entry in enumerate(self.pages(f"playlists/{playlist_id}/items?limit=50"), 1):
            track = (entry or {}).get("item") or (entry or {}).get("track")
            if not track or track.get("type", "track") != "track":
                skipped.append({"position": index, "reason": "Unavailable item or non-music item"})
                continue
            artist_genres = set()
            if include_genres:
                for artist in track.get("artists", []):
                    aid = artist.get("id")
                    if aid:
                        if aid not in genres:
                            genres[aid] = self.get(f"artists/{aid}").get("genres", [])
                        artist_genres.update(genres[aid])
            tracks.append({"position": index, "spotify_id": track.get("id"), "title": track.get("name", ""),
                           "artists": [a["name"] for a in track.get("artists", [])],
                           "album": (track.get("album") or {}).get("name", ""),
                           "year": (track.get("album") or {}).get("release_date", "")[:4],
                           "duration_ms": track.get("duration_ms"),
                           "isrc": (track.get("external_ids") or {}).get("isrc"),
                           "genres": sorted(artist_genres), "is_local": track.get("is_local", False)})
        return {"playlist_id": playlist_id, "tracks": tracks, "skipped": skipped}
