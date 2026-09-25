"""Core domain models for the Mood DJ system.

These types carry no framework dependencies. They describe the vocabulary of the
domain: strategies, target audio profiles, tracks, stages and the final decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Strategy(str, Enum):
    """The high-level approach Laya picks for a listening session."""

    ACCOMPANY = "accompany"
    LIFT = "lift"
    ENERGIZE = "energize"
    CALM = "calm"


@dataclass(frozen=True)
class MoodProfile:
    """A target audio profile Laya wants the catalog to match.

    All fields are normalized to the 0.0-1.0 range except tempo, which is in BPM.
    """

    energy: float
    valence: float
    tempo: float
    instrumentalness: float


@dataclass(frozen=True)
class Track:
    """A single track candidate, enriched with catalog features and cover art."""

    id: str
    name: str
    artist: str
    album: str
    energy: float
    valence: float
    tempo: float
    danceability: float
    acousticness: float
    instrumentalness: float
    cover_url: str | None = None
    external_url: str | None = None
    keep_probability: float | None = None


@dataclass(frozen=True)
class Stage:
    """One stage of the listening session: a target profile plus chosen tracks."""

    name: str
    profile: MoodProfile
    tracks: list[Track] = field(default_factory=list)


@dataclass(frozen=True)
class Decision:
    """The full decision trace returned to the caller for transparency."""

    strategy: Strategy
    strategy_probabilities: dict[str, float]
    stages: list[Stage] = field(default_factory=list)


class LyricsStatus(str, Enum):
    """The outcome of looking up lyrics for a track."""

    LYRICS = "lyrics"
    INSTRUMENTAL = "instrumental"
    MISSING = "missing"


@dataclass(frozen=True)
class LyricsEntry:
    """A cached lyrics lookup result for one Spotify track."""

    track_id: str
    status: LyricsStatus
    text: str | None
    fetched_at: str


@dataclass(frozen=True)
class SpotifyTokens:
    """OAuth tokens for one authenticated Spotify user session."""

    access_token: str
    refresh_token: str
    expires_at: float


@dataclass(frozen=True)
class PlaylistSummary:
    """A user playlist as listed by `GET /v1/me/playlists`."""

    id: str
    name: str
    image_url: str | None
    track_count: int
    snapshot_id: str


@dataclass(frozen=True)
class PlaylistTrack:
    """A single track inside a playlist, mapped from the Spotify API response."""

    id: str
    name: str
    artist: str
    album: str
    duration_s: float
    cover_url: str | None
    external_url: str | None


class PrepareState(str, Enum):
    """The lifecycle state of a playlist preparation job."""

    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class PrepareProgress:
    """Progress counters for a playlist preparation job."""

    state: PrepareState = PrepareState.IDLE
    total: int = 0
    processed: int = 0
    with_lyrics: int = 0
    instrumental: int = 0
    missing: int = 0
    error: str | None = None
