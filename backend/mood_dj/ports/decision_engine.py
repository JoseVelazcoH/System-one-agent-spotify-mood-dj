"""Port for the decision engine: turns a mood prompt into strategy and targets."""

from __future__ import annotations

from typing import Protocol

from mood_dj.domain.models import MoodProfile, Strategy, Track


class DecisionEngine(Protocol):
    """Decides strategy, target audio profile and per-track keep decisions."""

    def decide_strategy(self, prompt: str) -> tuple[Strategy, dict[str, float]]:
        """Pick the listening strategy for the given prompt.

        Returns the chosen strategy and the calibrated probability per candidate
        strategy (keyed by strategy value).
        """
        ...

    def decide_targets(self, prompt: str, strategy: Strategy, stage_name: str) -> MoodProfile:
        """Pick the target audio profile for a single stage of the session."""
        ...

    def decide_keep(self, prompt: str, track: Track) -> float:
        """Return the probability that a candidate track fits the current moment."""
        ...

    def decide_keep_many(self, prompt: str, tracks: list[Track]) -> list[float]:
        """Return the keep probability for each track, in the same order as `tracks`.

        Implementations should batch the underlying model calls where possible; this
        is the preferred entry point over calling `decide_keep` once per track.
        """
        ...
