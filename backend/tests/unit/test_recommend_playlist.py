"""Unit tests for the RecommendPlaylist use case, using fake adapters."""

from __future__ import annotations

from mood_dj.application.recommend_playlist import RecommendPlaylistUseCase
from mood_dj.domain.models import Strategy
from tests.unit.fakes import FakeCoverProvider, FakeDecisionEngine, FakeTrackCatalog


def test_lift_strategy_produces_multiple_stages() -> None:
    engine = FakeDecisionEngine(strategy=Strategy.LIFT)
    use_case = RecommendPlaylistUseCase(
        decision_engine=engine,
        catalog=FakeTrackCatalog(),
        cover_provider=FakeCoverProvider(),
    )

    decision = use_case.run("I am sad but want to feel better")

    assert decision.strategy is Strategy.LIFT
    assert len(decision.stages) > 1


def test_accompany_strategy_produces_single_stage() -> None:
    engine = FakeDecisionEngine(strategy=Strategy.ACCOMPANY)
    use_case = RecommendPlaylistUseCase(
        decision_engine=engine,
        catalog=FakeTrackCatalog(),
        cover_provider=FakeCoverProvider(),
    )

    decision = use_case.run("I want music that matches how I feel right now")

    assert decision.strategy is Strategy.ACCOMPANY
    assert len(decision.stages) == 1


def test_tracks_are_enriched_with_cover_and_external_url() -> None:
    use_case = RecommendPlaylistUseCase(
        decision_engine=FakeDecisionEngine(),
        catalog=FakeTrackCatalog(),
        cover_provider=FakeCoverProvider(),
    )

    decision = use_case.run("energize me for a run")

    for stage in decision.stages:
        for track in stage.tracks:
            assert track.cover_url is not None
            assert track.external_url is not None


def test_tracks_are_ranked_by_keep_probability_even_when_all_are_low() -> None:
    """Real Laya keep probabilities can all be low (e.g. 0.02-0.37); a stage must
    still be populated by ranking, not emptied by a hard threshold."""
    catalog = FakeTrackCatalog()
    engine = FakeDecisionEngine(keep_probabilities=[0.05, 0.37, 0.02, 0.2, 0.1])
    use_case = RecommendPlaylistUseCase(
        decision_engine=engine,
        catalog=catalog,
        cover_provider=FakeCoverProvider(),
        tracks_per_stage=3,
    )

    decision = use_case.run("calm me down before sleep")

    for stage in decision.stages:
        assert len(stage.tracks) == 3
        probabilities = [track.keep_probability for track in stage.tracks]
        assert probabilities == sorted(probabilities, reverse=True)


def test_keep_probability_is_requested_in_a_single_batch_call() -> None:
    engine = FakeDecisionEngine()
    use_case = RecommendPlaylistUseCase(
        decision_engine=engine,
        catalog=FakeTrackCatalog(),
        cover_provider=FakeCoverProvider(),
    )

    use_case.run("energize me for a run")

    assert len(engine.keep_many_calls) == len(engine.target_calls)
    for _, tracks in engine.keep_many_calls:
        assert len(tracks) == len(FakeTrackCatalog().tracks)


def test_strategy_probabilities_are_carried_in_decision() -> None:
    probabilities = {"accompany": 0.05, "lift": 0.05, "energize": 0.85, "calm": 0.05}
    engine = FakeDecisionEngine(strategy=Strategy.ENERGIZE, strategy_probabilities=probabilities)
    use_case = RecommendPlaylistUseCase(
        decision_engine=engine,
        catalog=FakeTrackCatalog(),
        cover_provider=FakeCoverProvider(),
    )

    decision = use_case.run("I need energy for the gym")

    assert decision.strategy_probabilities == probabilities
