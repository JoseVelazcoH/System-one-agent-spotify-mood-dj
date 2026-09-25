"""Unit tests for the /playlists endpoints, with adapters replaced by fakes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from mood_dj.api.deps import (
    get_current_tokens,
    get_job_manager,
    get_playlists_client,
    get_recommend_job_manager,
    get_session_id,
)
from mood_dj.api.main import app
from mood_dj.application.recommend_from_playlist import (
    PlaylistRecommendation,
    PlaylistStage,
    RankedTrack,
)
from mood_dj.application.recommend_job_manager import RecommendJobProgress, RecommendJobState
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


class FakeRecommendJobManager:
    def __init__(self, job: RecommendJobProgress | None = None) -> None:
        self.job = job
        self.started: list[tuple[str, str, str, str]] = []

    def start(self, session_id, playlist_id, prompt, access_token) -> str:
        self.started.append((session_id, playlist_id, prompt, access_token))
        return "job-1"

    def status(self, job_id: str) -> RecommendJobProgress | None:
        if job_id != "job-1":
            return None
        return self.job


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
    app.dependency_overrides[get_session_id] = lambda: "session-1"
    client = TestClient(app)

    response = client.post("/playlists/pl1/recommend", json={"prompt": "sad"})

    assert response.status_code == 409


def test_recommend_starts_job_and_returns_job_id_when_prepared() -> None:
    app.dependency_overrides[get_current_tokens] = lambda: SpotifyTokens(
        access_token="tok", refresh_token="ref", expires_at=99999999999.0
    )
    app.dependency_overrides[get_job_manager] = lambda: DoneJobManager()
    app.dependency_overrides[get_session_id] = lambda: "session-1"
    job_manager = FakeRecommendJobManager()
    app.dependency_overrides[get_recommend_job_manager] = lambda: job_manager
    client = TestClient(app)

    response = client.post("/playlists/pl1/recommend", json={"prompt": "I feel sad"})

    assert response.status_code == 202
    assert response.json() == {"job_id": "job-1"}
    assert len(job_manager.started) == 1
    session_id, playlist_id, prompt, access_token = job_manager.started[0]
    assert isinstance(session_id, str) and session_id
    assert (playlist_id, prompt, access_token) == ("pl1", "I feel sad", "tok")


def test_recommend_job_status_requires_session() -> None:
    client = TestClient(app)

    response = client.get("/recommend-jobs/job-1")

    assert response.status_code == 401


def test_recommend_job_status_returns_404_for_unknown_job() -> None:
    app.dependency_overrides[get_current_tokens] = lambda: SpotifyTokens(
        access_token="tok", refresh_token="ref", expires_at=99999999999.0
    )
    app.dependency_overrides[get_recommend_job_manager] = lambda: FakeRecommendJobManager(job=None)
    client = TestClient(app)

    response = client.get("/recommend-jobs/unknown")

    assert response.status_code == 404


def test_recommend_job_status_reports_running_progress() -> None:
    app.dependency_overrides[get_current_tokens] = lambda: SpotifyTokens(
        access_token="tok", refresh_token="ref", expires_at=99999999999.0
    )
    job = RecommendJobProgress(state=RecommendJobState.RUNNING, phase="judging lyrics", processed=3, total=10)
    app.dependency_overrides[get_recommend_job_manager] = lambda: FakeRecommendJobManager(job=job)
    client = TestClient(app)

    response = client.get("/recommend-jobs/job-1")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "running"
    assert body["phase"] == "judging lyrics"
    assert body["processed"] == 3
    assert body["total"] == 10
    assert body["result"] is None


def test_recommend_job_status_returns_mapped_result_when_done() -> None:
    app.dependency_overrides[get_current_tokens] = lambda: SpotifyTokens(
        access_token="tok", refresh_token="ref", expires_at=99999999999.0
    )
    job = RecommendJobProgress(
        state=RecommendJobState.DONE, phase="building playlist", processed=1, total=1, result=_sample_recommendation()
    )
    app.dependency_overrides[get_recommend_job_manager] = lambda: FakeRecommendJobManager(job=job)
    client = TestClient(app)

    response = client.get("/recommend-jobs/job-1")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "done"
    assert body["result"]["strategy"] == "accompany"
    assert body["result"]["stages"][0]["tracks"][0]["keep_probability"] == 0.8


def test_recommend_job_status_reports_error() -> None:
    app.dependency_overrides[get_current_tokens] = lambda: SpotifyTokens(
        access_token="tok", refresh_token="ref", expires_at=99999999999.0
    )
    job = RecommendJobProgress(state=RecommendJobState.ERROR, error="boom")
    app.dependency_overrides[get_recommend_job_manager] = lambda: FakeRecommendJobManager(job=job)
    client = TestClient(app)

    response = client.get("/recommend-jobs/job-1")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "error"
    assert body["error"] == "boom"
