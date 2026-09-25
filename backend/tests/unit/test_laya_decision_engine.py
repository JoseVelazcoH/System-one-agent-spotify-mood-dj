"""Unit tests for the Laya adapter's pure helpers and batching, using a fake router.

These tests never load the real model: `Router` is replaced by a small fake object
so they run fast and are safe for the default `uv run pytest` suite.
"""

from __future__ import annotations

from mood_dj.adapters.laya_decision_engine import (
    KEEP_QUESTION_ID,
    LayaDecisionEngine,
    describe_track_in_words,
)
from mood_dj.domain.models import Track


def _track(**overrides) -> Track:
    defaults = dict(
        id="1",
        name="Test Song",
        artist="Test Artist",
        album="Test Album",
        energy=0.85,
        valence=0.1,
        tempo=150.0,
        danceability=0.4,
        acousticness=0.05,
        instrumentalness=0.02,
    )
    defaults.update(overrides)
    return Track(**defaults)


class FakeRouter:
    """Records predict_batch calls and returns a fixed noul probability per request."""

    def __init__(self, probabilities: list[float]) -> None:
        self.probabilities = probabilities
        self.predict_batch_calls: list[tuple[list[dict], int | None]] = []

    def predict_batch(self, requests, batch_size=None):
        self.predict_batch_calls.append((list(requests), batch_size))
        return [{"answers": {KEEP_QUESTION_ID: {"noul": p}}} for p in self.probabilities]


def test_describe_track_in_words_reports_high_energy_fast_tempo() -> None:
    track = _track(energy=0.9, valence=0.85, tempo=150.0, instrumentalness=0.02, acousticness=0.05)

    description = describe_track_in_words(track)

    assert "energy: high" in description
    assert "mood: happy" in description
    assert "150" in description
    assert "vocal" in description


def test_describe_track_in_words_reports_low_energy_sad_slow_acoustic() -> None:
    track = _track(energy=0.15, valence=0.1, tempo=70.0, instrumentalness=0.05, acousticness=0.9)

    description = describe_track_in_words(track)

    assert "energy: low" in description
    assert "sad" in description or "melancholic" in description
    assert "slow" in description
    assert "acoustic" in description


def test_describe_track_in_words_reports_instrumental_when_vocals_are_low() -> None:
    track = _track(instrumentalness=0.9)

    description = describe_track_in_words(track)

    assert "instrumental" in description


def test_decide_keep_many_returns_probabilities_in_input_order() -> None:
    router = FakeRouter(probabilities=[0.12, 0.37, 0.02])
    engine = LayaDecisionEngine(router=router)
    tracks = [_track(id=str(i)) for i in range(3)]

    result = engine.decide_keep_many("I am sad but want to feel better", tracks)

    assert result == [0.12, 0.37, 0.02]


def test_decide_keep_many_uses_a_single_batch_call() -> None:
    router = FakeRouter(probabilities=[0.5, 0.5])
    engine = LayaDecisionEngine(router=router)
    tracks = [_track(id=str(i)) for i in range(2)]

    engine.decide_keep_many("calm me down", tracks)

    assert len(router.predict_batch_calls) == 1
    requests, _ = router.predict_batch_calls[0]
    assert len(requests) == 2
    for request in requests:
        assert "state" in request
        assert "questions" in request
        assert request["questions"][KEEP_QUESTION_ID]["type"] == "noul"


def test_decide_keep_many_returns_empty_list_for_no_tracks() -> None:
    router = FakeRouter(probabilities=[])
    engine = LayaDecisionEngine(router=router)

    result = engine.decide_keep_many("anything", [])

    assert result == []
    assert router.predict_batch_calls == []
