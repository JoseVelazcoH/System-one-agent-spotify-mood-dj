"""Port for judging a listener's mood and per-track lyrics fit with Laya."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mood_dj.domain.models import PlaylistTrack, Strategy
from mood_dj.domain.playlist_strategy import PlaylistSignals


@dataclass(frozen=True)
class TrackLyrics:
    """A playlist track paired with its (already truncated) lyrics text."""

    track: PlaylistTrack
    text: str


@dataclass(frozen=True)
class TrackJudgment:
    """Laya's judgment of one track's lyrics for the current prompt.

    `tone` is prompt-independent (the emotional tone of the lyrics themselves,
    0.0 very sad to 1.0 very happy). `fit` is prompt-dependent: the probability
    that these lyrics fit what the listener asked for.
    """

    track_id: str
    tone: float
    fit: float


class LyricsJudge(Protocol):
    """Judges mood signals and lyrics fit using the multilingual Laya checkpoint."""

    def detect_signals(self, prompt: str) -> tuple[PlaylistSignals, dict[str, float]]:
        """Return the boolean mood signals plus their raw probabilities."""
        ...

    def judge_lyrics(
        self, prompt: str, strategy: Strategy, tracks: list[TrackLyrics]
    ) -> list[TrackJudgment]:
        """Judge tone and fit for each track, in the same order as `tracks`."""
        ...
