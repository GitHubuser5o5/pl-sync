import unittest
from spot2rb.core.spotify import Spotify, SpotifyError


class PlaylistFilterTests(unittest.TestCase):
    def client(self, me):
        client = Spotify("id")
        items = [{"id": "mine", "owner": {"id": "lu"}}, {"id": "saved", "owner": {"id": "other"}},
                 {"id": "collab", "owner": {"id": "other"}, "collaborative": True}]
        def get(path):
            if path == "me":
                if isinstance(me, Exception):
                    raise me
                return {"id": me}
            return {"items": items, "next": None}
        client.get = get
        return client

    def test_hides_playlists_spotify_will_not_open(self):
        client = self.client("lu")
        self.assertEqual([p["id"] for p in client.playlists()], ["mine", "collab"])
        self.assertEqual(client.hidden, 1)

    def test_keeps_everything_when_user_unknown(self):
        client = self.client(SpotifyError("no"))
        self.assertEqual(len(client.playlists()), 3)
        self.assertEqual(client.hidden, 0)


if __name__ == "__main__":
    unittest.main()
