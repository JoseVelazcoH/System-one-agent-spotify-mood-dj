"""Unit tests for the SpotifyPlaylistsClient adapter, using a fake HTTP client."""

from __future__ import annotations

from mood_dj.adapters.spotify_playlists import (
    HttpxSpotifyPlaylistsHttpClient,
    PLAYLISTS_URL,
    SpotifyPlaylistsClient,
    playlist_items_url,
)


class FakeHttpClient:
    """Fakes GET requests by returning a fixed page per exact URL."""

    def __init__(self, pages: dict[str, dict]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def get(self, url: str, access_token: str) -> dict:
        self.calls.append(url)
        return self.pages[url]


def test_list_playlists_maps_fields() -> None:
    http = FakeHttpClient(
        {
            PLAYLISTS_URL + "?limit=50": {
                "items": [
                    {
                        "id": "pl1",
                        "name": "My Playlist",
                        "images": [{"url": "https://img/1.jpg"}],
                        "tracks": {"total": 42},
                        "snapshot_id": "snap1",
                    }
                ],
                "next": None,
            }
        }
    )
    client = SpotifyPlaylistsClient(http_client=http)

    playlists = client.list_playlists("token")

    assert len(playlists) == 1
    assert playlists[0].id == "pl1"
    assert playlists[0].name == "My Playlist"
    assert playlists[0].image_url == "https://img/1.jpg"
    assert playlists[0].track_count == 42
    assert playlists[0].snapshot_id == "snap1"


def test_list_playlists_handles_missing_images() -> None:
    http = FakeHttpClient(
        {
            PLAYLISTS_URL + "?limit=50": {
                "items": [{"id": "pl1", "name": "No Cover", "images": [], "tracks": {"total": 0}, "snapshot_id": "s"}],
                "next": None,
            }
        }
    )
    client = SpotifyPlaylistsClient(http_client=http)

    playlists = client.list_playlists("token")

    assert playlists[0].image_url is None


def test_list_playlists_follows_pagination() -> None:
    next_url = PLAYLISTS_URL + "?offset=1&limit=1"
    http = FakeHttpClient(
        {
            PLAYLISTS_URL + "?limit=50": {
                "items": [{"id": "pl1", "name": "A", "images": [], "tracks": {"total": 1}, "snapshot_id": "s"}],
                "next": next_url,
            },
            next_url: {
                "items": [{"id": "pl2", "name": "B", "images": [], "tracks": {"total": 1}, "snapshot_id": "s"}],
                "next": None,
            },
        }
    )
    client = SpotifyPlaylistsClient(http_client=http)

    playlists = client.list_playlists("token")

    assert [p.id for p in playlists] == ["pl1", "pl2"]


def _track_entry(track_id: str, key: str = "track") -> dict:
    return {
        key: {
            "id": track_id,
            "name": f"Song {track_id}",
            "artists": [{"name": "Artist One"}, {"name": "Artist Two"}],
            "album": {"name": "Album", "images": [{"url": "https://img/cover.jpg"}]},
            "duration_ms": 210000,
            "external_urls": {"spotify": f"https://open.spotify.com/track/{track_id}"},
        }
    }


def test_get_playlist_tracks_uses_item_key_with_track_fallback() -> None:
    url = playlist_items_url("pl1")
    http = FakeHttpClient(
        {url + "?limit=50": {"items": [_track_entry("t1", key="item"), _track_entry("t2", key="track")], "next": None}}
    )
    client = SpotifyPlaylistsClient(http_client=http)

    tracks = client.get_playlist_tracks("pl1", "token")

    assert [t.id for t in tracks] == ["t1", "t2"]
    assert tracks[0].artist == "Artist One"
    assert tracks[0].album == "Album"
    assert tracks[0].duration_s == 210.0
    assert tracks[0].cover_url == "https://img/cover.jpg"
    assert tracks[0].external_url == "https://open.spotify.com/track/t1"


def test_get_playlist_tracks_skips_null_local_and_episode_entries() -> None:
    local_track = _track_entry("local1", key="track")
    local_track["track"]["is_local"] = True
    episode = {"track": {"id": "ep1", "type": "episode"}}
    url = playlist_items_url("pl1")
    http = FakeHttpClient(
        {
            url + "?limit=50": {
                "items": [
                    {"track": None},
                    local_track,
                    episode,
                    _track_entry("t1", key="track"),
                ],
                "next": None,
            }
        }
    )
    client = SpotifyPlaylistsClient(http_client=http)

    tracks = client.get_playlist_tracks("pl1", "token")

    assert [t.id for t in tracks] == ["t1"]


def test_get_playlist_tracks_follows_pagination() -> None:
    url = playlist_items_url("pl1")
    next_url = url + "?offset=1&limit=1"
    http = FakeHttpClient(
        {
            url + "?limit=50": {"items": [_track_entry("t1", key="track")], "next": next_url},
            next_url: {"items": [_track_entry("t2", key="track")], "next": None},
        }
    )
    client = SpotifyPlaylistsClient(http_client=http)

    tracks = client.get_playlist_tracks("pl1", "token")

    assert [t.id for t in tracks] == ["t1", "t2"]


def test_httpx_client_can_be_constructed() -> None:
    HttpxSpotifyPlaylistsHttpClient()
