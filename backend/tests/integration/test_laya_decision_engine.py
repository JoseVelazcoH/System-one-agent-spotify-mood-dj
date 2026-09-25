"""Integration test against the real Laya model.

Marked `laya` so it is skipped by default (it downloads real model weights and runs
actual inference). Run explicitly with: `uv run pytest -m laya`.
"""

from __future__ import annotations

import pytest

from mood_dj.adapters.laya_decision_engine import LayaDecisionEngine
from mood_dj.domain.models import Strategy, Track

pytestmark = pytest.mark.laya


def test_decide_strategy_returns_a_valid_strategy_with_probabilities() -> None:
    engine = LayaDecisionEngine()

    strategy, probabilities = engine.decide_strategy("I am sad but want to feel better")

    assert isinstance(strategy, Strategy)
    assert set(probabilities) == {s.value for s in Strategy}
    assert abs(sum(probabilities.values()) - 1.0) < 0.01


def test_decide_targets_returns_normalized_profile() -> None:
    engine = LayaDecisionEngine()

    profile = engine.decide_targets("I need energy for the gym", Strategy.ENERGIZE, "session")

    assert 0.0 <= profile.energy <= 1.0
    assert 0.0 <= profile.valence <= 1.0
    assert 0.0 <= profile.instrumentalness <= 1.0
    assert profile.tempo > 0


def test_decide_keep_returns_a_probability() -> None:
    engine = LayaDecisionEngine()
    track = Track(
        id="1",
        name="Test Song",
        artist="Test Artist",
        album="Test Album",
        energy=0.8,
        valence=0.8,
        tempo=128.0,
        danceability=0.7,
        acousticness=0.1,
        instrumentalness=0.05,
    )

    probability = engine.decide_keep("I need energy for the gym", track)

    assert 0.0 <= probability <= 1.0
