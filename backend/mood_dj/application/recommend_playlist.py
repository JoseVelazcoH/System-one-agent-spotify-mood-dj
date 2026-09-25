"""Use case: turn a natural-language mood prompt into a decided playlist."""

from __future__ import annotations

from mood_dj.domain.models import Decision, Stage, Strategy
from mood_dj.ports.cover_provider import CoverProvider
from mood_dj.ports.decision_engine import DecisionEngine
from mood_dj.ports.track_catalog import TrackCatalog

CANDIDATES_PER_STAGE = 12
TRACKS_PER_STAGE = 6
# A very low floor: candidates below this are almost certainly a bad fit and are
# excluded even if there are not enough higher-scoring candidates to fill a stage.
MINIMUM_KEEP_PROBABILITY = 0.01

LIFT_STAGE_NAMES = ["melancholic", "hopeful", "positive"]
SINGLE_STAGE_NAME = "session"


class RecommendPlaylistUseCase:
    """Orchestrates the decision engine, catalog and cover provider ports."""

    def __init__(
        self,
        decision_engine: DecisionEngine,
        catalog: TrackCatalog,
        cover_provider: CoverProvider,
        candidates_per_stage: int = CANDIDATES_PER_STAGE,
        tracks_per_stage: int = TRACKS_PER_STAGE,
        minimum_keep_probability: float = MINIMUM_KEEP_PROBABILITY,
    ) -> None:
        self._decision_engine = decision_engine
        self._catalog = catalog
        self._cover_provider = cover_provider
        self._candidates_per_stage = candidates_per_stage
        self._tracks_per_stage = tracks_per_stage
        self._minimum_keep_probability = minimum_keep_probability

    def run(self, prompt: str) -> Decision:
        strategy, strategy_probabilities = self._decision_engine.decide_strategy(prompt)
        stage_names = self._stage_names_for(strategy)

        stages: list[Stage] = []
        for stage_name in stage_names:
            profile = self._decision_engine.decide_targets(prompt, strategy, stage_name)
            candidates = self._catalog.find_candidates(profile, self._candidates_per_stage)
            ranked = self._rank_by_keep_probability(prompt, candidates)
            enriched = self._cover_provider.enrich(ranked[: self._tracks_per_stage])
            stages.append(Stage(name=stage_name, profile=profile, tracks=enriched))

        return Decision(
            strategy=strategy,
            strategy_probabilities=strategy_probabilities,
            stages=stages,
        )

    def _stage_names_for(self, strategy: Strategy) -> list[str]:
        if strategy is Strategy.LIFT:
            return LIFT_STAGE_NAMES
        return [SINGLE_STAGE_NAME]

    def _rank_by_keep_probability(self, prompt: str, candidates: list) -> list:
        """Rank candidates by keep probability, highest first.

        Real Laya keep probabilities observed in practice are low in absolute terms
        (e.g. 0.02-0.37), so a hard threshold would leave a stage empty. Ranking
        guarantees a populated stage whenever candidates exist, with only a very
        low floor excluding near-zero fits.
        """
        if not candidates:
            return []
        probabilities = self._decision_engine.decide_keep_many(prompt, candidates)
        scored = [
            (probability, track.__class__(**{**track.__dict__, "keep_probability": probability}))
            for track, probability in zip(candidates, probabilities)
            if probability >= self._minimum_keep_probability
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [track for _, track in scored]
