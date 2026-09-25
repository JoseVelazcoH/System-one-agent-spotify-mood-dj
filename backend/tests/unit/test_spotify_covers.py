"""Unit tests for the Spotify cover provider adapter, using a fake HTTP client."""

from __future__ import annotations

from mood_dj.adapters.spotify_covers import SpotifyCoverProvider
from mood_dj.domain.models import Track


class FakeSpotifyHttpClient:
    """Fakes the two Spotify endpoints the adapter needs: token and single track."""

    def __init__(self) -> None:
        self.token_requests = 0
        self.track_requests: list[str] = []

    def post_token(self, client_id: str, client_secret: str) -> str:
        self.token_requests += 1
        return "fake-access-token"

    def get_track(self, track_id: str, access_token: str) -> dict | None:
        self.track_requests.append(track_id)
        return {
            "id": track_id,
            "album": {"images": [{"url": f"https://img.example/{track_id}.jpg"}]},
            "external_urls": {"spotify": f"https://open.spotify.com/track/{track_id}"},
        }


def _track(track_id: str) -> Track:
    return Track(
        id=track_id,
        name="Song",
        artist="Artist",
        album="Album",
        energy=0.5,
        valence=0.5,
        tempo=120.0,
        danceability=0.5,
        acousticness=0.1,
        instrumentalness=0.1,
    )


def test_enrich_fills_cover_and_external_url() -> None:
    http = FakeSpotifyHttpClient()
    provider = SpotifyCoverProvider(client_id="id", client_secret="secret", http_client=http)

    enriched = provider.enrich([_track("t1"), _track("t2")])

    assert enriched[0].cover_url == "https://img.example/t1.jpg"
    assert enriched[0].external_url == "https://open.spotify.com/track/t1"
    assert enriched[1].cover_url == "https://img.example/t2.jpg"
    assert http.token_requests == 1


def test_enrich_requests_each_track_individually_and_keeps_order() -> None:
    # Spotify answers 403 to the batch `GET /v1/tracks?ids=` for this app tier,
    # while the single-track endpoint works, so the adapter must use the latter.
    http = FakeSpotifyHttpClient()
    provider = SpotifyCoverProvider(client_id="id", client_secret="secret", http_client=http)
    tracks = [_track(f"t{i}") for i in range(8)]

    enriched = provider.enrich(tracks)

    assert sorted(http.track_requests) == sorted(track.id for track in tracks)
    assert [track.id for track in enriched] == [track.id for track in tracks]
    assert http.token_requests == 1


def test_enrich_leaves_track_unmodified_when_lookup_fails() -> None:
    class FailingHttpClient(FakeSpotifyHttpClient):
        def get_track(self, track_id: str, access_token: str) -> dict | None:
            if track_id == "broken":
                raise RuntimeError("spotify unavailable")
            return super().get_track(track_id, access_token)

    provider = SpotifyCoverProvider(client_id="id", client_secret="secret", http_client=FailingHttpClient())

    enriched = provider.enrich([_track("broken"), _track("ok")])

    assert enriched[0].cover_url is None
    assert enriched[1].cover_url == "https://img.example/ok.jpg"


def test_enrich_leaves_track_unmodified_when_not_found() -> None:
    http = FakeSpotifyHttpClient()

    class MissingTrackHttpClient(FakeSpotifyHttpClient):
        def get_track(self, track_id: str, access_token: str) -> dict | None:
            return None

    provider = SpotifyCoverProvider(client_id="id", client_secret="secret", http_client=MissingTrackHttpClient())

    enriched = provider.enrich([_track("missing")])

    assert enriched[0].cover_url is None
    assert enriched[0].external_url is None
