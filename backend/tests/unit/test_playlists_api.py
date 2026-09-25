"""Unit tests for the /playlists endpoints, with adapters replaced by fakes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from mood_dj.api.deps import (
    get_current_tokens,
    get_job_manager,
    get_playlists_client,
    get_recommend_from_playlist_use_case,
)
from mood_dj.api.main import app
from mood_dj.application.recommend_from_playlist import (
    PlaylistNotPreparedError,
    PlaylistRecommendation,
    PlaylistStage,
    RankedTrack,
)
from mood_dj.domain.models import PlaylistSummary, PlaylistTrack, PrepareProgress, PrepareState, SpotifyTokens, Strategy


class FakePlaylistsClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def list_playlists(self, access_token: str):
        self.calls.append(access_token)
        return [PlaylistSummary(id="pl1", name="My Playlist", image_url=None, track_count=10, snapshot_id="s")]

    def get_playlist_tracks(self, playlist_id: str, access_token: str):
        return []


class FakeJobManager:
    def __init__(self) -> None:
        self.started: list[tuple[str, str]] = []
        self._status = PrepareProgress(state=PrepareState.RUNNING, total=10, processed=3, with_lyrics=2, instrumental=1)

    def start(self, playlist_id: str, access_token: str) -> bool:
        self.started.append((playlist_id, access_token))
        return True

    def status(self, playlist_id: str) -> PrepareProgress:
        return self._status


def teardown_function() -> None:
    app.dependency_overrides = {}


def test_list_playlists_requires_session() -> None:
    client = TestClient(app)

    response = client.get("/playlists")

    assert response.status_code == 401


def test_list_playlists_returns_mapped_summaries() -> None:
    app.dependency_overrides[get_current_tokens] = lambda: SpotifyTokens(
        access_token="tok", refresh_token="ref", expires_at=99999999999.0
    )
    app.dependency_overrides[get_playlists_client] = lambda: FakePlaylistsClient()
    client = TestClient(app)

    response = client.get("/playlists")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == "pl1"
    assert body[0]["name"] == "My Playlist"


def test_prepare_endpoint_starts_job() -> None:
    job_manager = FakeJobManager()
    app.dependency_overrides[get_current_tokens] = lambda: SpotifyTokens(
        access_token="tok", refresh_token="ref", expires_at=99999999999.0
    )
    app.dependency_overrides[get_job_manager] = lambda: job_manager
    client = TestClient(app)

    response = client.post("/playlists/pl1/prepare")

    assert response.status_code == 200
    assert response.json() == {"started": True}
    assert job_manager.started == [("pl1", "tok")]


def test_status_endpoint_returns_progress_counts() -> None:
    app.dependency_overrides[get_current_tokens] = lambda: SpotifyTokens(
        access_token="tok", refresh_token="ref", expires_at=99999999999.0
    )
    app.dependency_overrides[get_job_manager] = lambda: FakeJobManager()
    client = TestClient(app)

    response = client.get("/playlists/pl1/status")

    body = response.json()
    assert body["state"] == "running"
    assert body["total"] == 10
    assert body["processed"] == 3
    assert body["with_lyrics"] == 2
    assert body["instrumental"] == 1


def test_prepare_requires_session() -> None:
    client = TestClient(app)

    response = client.post("/playlists/pl1/prepare")

    assert response.status_code == 401


def test_status_requires_session() -> None:
    client = TestClient(app)

    response = client.get("/playlists/pl1/status")

    assert response.status_code == 401


class DoneJobManager(FakeJobManager):
    def __init__(self) -> None:
        super().__init__()
        self._status = PrepareProgress(state=PrepareState.DONE, total=1, processed=1, with_lyrics=1)


class FakeRecommendUseCase:
    def __init__(self, recommendation=None, error: Exception | None = None) -> None:
        self.recommendation = recommendation
        self.error = error
        self.calls: list[tuple[str, str, str]] = []

    def run(self, prompt, playlist_id, access_token):
        self.calls.append((prompt, playlist_id, access_token))
        if self.error is not None:
            raise self.error
        return self.recommendation


def _sample_recommendation() -> PlaylistRecommendation:
    track = PlaylistTrack(
        id="t1", name="Song", artist="Artist", album="Album", duration_s=200.0,
        cover_url="https://cover", external_url="https://open",
    )
    return PlaylistRecommendation(
        strategy=Strategy.ACCOMPANY,
        signal_probabilities={"feels_bad": 0.9, "wants_change": 0.1, "wants_energy": 0.1, "wants_rest": 0.1},
        stages=[PlaylistStage(name="session", tracks=[RankedTrack(track=track, tone=0.3, fit=0.8)])],
        excluded_no_lyrics=2,
        excluded_instrumental=1,
    )


def test_recommend_requires_session() -> None:
    client = TestClient(app)

    response = client.post("/playlists/pl1/recommend", json={"prompt": "sad"})

    assert response.status_code == 401


def test_recommend_returns_409_when_not_prepared() -> None:
    app.dependency_overrides[get_current_tokens] = lambda: SpotifyTokens(
        access_token="tok", refresh_token="ref", expires_at=99999999999.0
    )
    app.dependency_overrides[get_job_manager] = lambda: FakeJobManager()  # state=running
    client = TestClient(app)

    response = client.post("/playlists/pl1/recommend", json={"prompt": "sad"})

    assert response.status_code == 409


def test_recommend_returns_mapped_decision_when_prepared() -> None:
    app.dependency_overrides[get_current_tokens] = lambda: SpotifyTokens(
        access_token="tok", refresh_token="ref", expires_at=99999999999.0
    )
    app.dependency_overrides[get_job_manager] = lambda: DoneJobManager()
    app.dependency_overrides[get_recommend_from_playlist_use_case] = lambda: FakeRecommendUseCase(
        recommendation=_sample_recommendation()
    )
    client = TestClient(app)

    response = client.post("/playlists/pl1/recommend", json={"prompt": "I feel sad"})

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "accompany"
    assert body["excluded"] == {"no_lyrics": 2, "instrumental": 1}
    assert body["stages"][0]["tracks"][0]["keep_probability"] == 0.8
    assert body["stages"][0]["tracks"][0]["tone"] == 0.3


def test_recommend_returns_409_when_use_case_reports_not_prepared() -> None:
    app.dependency_overrides[get_current_tokens] = lambda: SpotifyTokens(
        access_token="tok", refresh_token="ref", expires_at=99999999999.0
    )
    app.dependency_overrides[get_job_manager] = lambda: DoneJobManager()
    app.dependency_overrides[get_recommend_from_playlist_use_case] = lambda: FakeRecommendUseCase(
        error=PlaylistNotPreparedError("not prepared")
    )
    client = TestClient(app)

    response = client.post("/playlists/pl1/recommend", json={"prompt": "sad"})

    assert response.status_code == 409
