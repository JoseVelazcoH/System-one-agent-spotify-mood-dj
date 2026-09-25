"""Unit tests for the FastAPI HTTP layer, with the use case dependency overridden."""

from __future__ import annotations

from fastapi.testclient import TestClient

from mood_dj.api.main import app, get_use_case
from mood_dj.application.recommend_playlist import RecommendPlaylistUseCase
from tests.unit.fakes import FakeCoverProvider, FakeDecisionEngine, FakeTrackCatalog


def _fake_use_case() -> RecommendPlaylistUseCase:
    return RecommendPlaylistUseCase(
        decision_engine=FakeDecisionEngine(),
        catalog=FakeTrackCatalog(),
        cover_provider=FakeCoverProvider(),
    )


def test_recommend_returns_decision_trace_and_tracks(monkeypatch) -> None:
    app.dependency_overrides = {}
    monkeypatch.setattr("mood_dj.api.main.get_use_case", _fake_use_case)
    monkeypatch.setattr("mood_dj.api.main.dataset_exists", lambda settings: True)
    monkeypatch.setattr(get_use_case, "cache_clear", lambda: None, raising=False)

    client = TestClient(app)
    response = client.post("/recommend", json={"prompt": "I am sad but want to feel better"})

    assert response.status_code == 200
    body = response.json()
    assert "strategy" in body
    assert "strategy_probabilities" in body
    assert len(body["stages"]) >= 1
    assert body["stages"][0]["tracks"][0]["cover_url"].startswith("https://")


def test_recommend_returns_503_when_dataset_missing(monkeypatch) -> None:
    monkeypatch.setattr("mood_dj.api.main.dataset_exists", lambda settings: False)

    client = TestClient(app)
    response = client.post("/recommend", json={"prompt": "anything"})

    assert response.status_code == 503


def test_health_endpoint_reports_status() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
