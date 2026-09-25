"""Pydantic request/response models for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel


class RecommendRequest(BaseModel):
    prompt: str


class TrackResponse(BaseModel):
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
    cover_url: str | None
    external_url: str | None
    keep_probability: float | None


class ProfileResponse(BaseModel):
    energy: float
    valence: float
    tempo: float
    instrumentalness: float


class StageResponse(BaseModel):
    name: str
    profile: ProfileResponse
    tracks: list[TrackResponse]


class RecommendResponse(BaseModel):
    strategy: str
    strategy_probabilities: dict[str, float]
    stages: list[StageResponse]


class MeResponse(BaseModel):
    logged_in: bool


class PlaylistSummaryResponse(BaseModel):
    id: str
    name: str
    image_url: str | None
    track_count: int
    snapshot_id: str


class RecommendFromPlaylistRequest(BaseModel):
    prompt: str


class PlaylistTrackResponse(BaseModel):
    id: str
    name: str
    artist: str
    album: str
    cover_url: str | None
    external_url: str | None
    keep_probability: float
    tone: float


class PlaylistStageResponse(BaseModel):
    name: str
    tracks: list[PlaylistTrackResponse]


class ExcludedResponse(BaseModel):
    no_lyrics: int
    instrumental: int


class PlaylistRecommendResponse(BaseModel):
    strategy: str
    signals: dict[str, float]
    stages: list[PlaylistStageResponse]
    excluded: ExcludedResponse


class PrepareStatusResponse(BaseModel):
    state: str
    total: int
    processed: int
    with_lyrics: int
    instrumental: int
    missing: int
    error: str | None = None
