"""Fake adapters implementing the application ports, used for fast unit tests."""

from __future__ import annotations

from mood_dj.domain.models import MoodProfile, Strategy, Track


class FakeDecisionEngine:
    """A scripted decision engine that returns fixed answers for tests."""

    def __init__(
        self,
        strategy: Strategy = Strategy.LIFT,
        strategy_probabilities: dict[str, float] | None = None,
        keep_probability: float = 0.9,
        keep_probabilities: list[float] | None = None,
    ) -> None:
        self.strategy = strategy
        self.strategy_probabilities = strategy_probabilities or {
            "accompany": 0.1,
            "lift": 0.7,
            "energize": 0.1,
            "calm": 0.1,
        }
        self.keep_probability = keep_probability
        self.keep_probabilities = keep_probabilities
        self.target_calls: list[tuple[str, Strategy, str]] = []
        self.keep_many_calls: list[tuple[str, list[Track]]] = []

    def decide_strategy(self, prompt: str) -> tuple[Strategy, dict[str, float]]:
        return self.strategy, self.strategy_probabilities

    def decide_targets(self, prompt: str, strategy: Strategy, stage_name: str) -> MoodProfile:
        self.target_calls.append((prompt, strategy, stage_name))
        return MoodProfile(energy=0.5, valence=0.5, tempo=110.0, instrumentalness=0.2)

    def decide_keep(self, prompt: str, track: Track) -> float:
        return self.keep_probability

    def decide_keep_many(self, prompt: str, tracks: list[Track]) -> list[float]:
        self.keep_many_calls.append((prompt, tracks))
        if self.keep_probabilities is not None:
            return list(self.keep_probabilities[: len(tracks)])
        return [self.keep_probability for _ in tracks]


class FakeTrackCatalog:
    """A fake catalog returning a fixed pool of candidate tracks."""

    def __init__(self, tracks: list[Track] | None = None) -> None:
        self.tracks = tracks or [
            Track(
                id=f"track-{i}",
                name=f"Song {i}",
                artist=f"Artist {i}",
                album=f"Album {i}",
                energy=0.5,
                valence=0.5,
                tempo=110.0,
                danceability=0.5,
                acousticness=0.3,
                instrumentalness=0.1,
            )
            for i in range(5)
        ]

    def find_candidates(self, profile: MoodProfile, limit: int) -> list[Track]:
        return self.tracks[:limit]


class FakeCoverProvider:
    """A fake cover provider that stamps a predictable cover URL per track."""

    def enrich(self, tracks: list[Track]) -> list[Track]:
        return [
            Track(
                **{
                    **track.__dict__,
                    "cover_url": f"https://covers.example/{track.id}.jpg",
                    "external_url": f"https://open.spotify.com/track/{track.id}",
                }
            )
            for track in tracks
        ]
