"""Use case: rank a prepared playlist's tracks by lyrics fit for a mood prompt."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from mood_dj.domain.models import LyricsStatus, PlaylistTrack, Strategy
from mood_dj.domain.playlist_strategy import resolve_playlist_strategy
from mood_dj.ports.judgment_cache import JudgmentCache
from mood_dj.ports.lyrics_judge import LyricsJudge, TrackJudgment, TrackLyrics
from mood_dj.ports.lyrics_repository import LyricsRepository
from mood_dj.ports.spotify_playlists import SpotifyPlaylistsClient

logger = logging.getLogger(__name__)

DEFAULT_MAX_CANDIDATES = 120
DEFAULT_TRACKS_PER_STAGE = 5
DEFAULT_LYRICS_TRUNCATE_CHARS = 1500
QUESTION_SET_VERSION = "v1"

LIFT_STAGE_NAMES = ["melancholic", "hopeful", "positive"]
SINGLE_STAGE_NAME = "session"

# Tone bands for the "lift" strategy: melancholic < hopeful < positive.
LIFT_BAND_BOUNDS = [(0.0, 0.4), (0.4, 0.7), (0.7, 1.01)]


class PlaylistNotPreparedError(Exception):
    """Raised when a playlist has no cached lyrics at all: /prepare was never run."""


class RecommendPhase(str, Enum):
    """The stage a recommendation run is currently in, for progress reporting."""

    DETECTING_MOOD = "detecting mood"
    JUDGING_LYRICS = "judging lyrics"
    BUILDING_PLAYLIST = "building playlist"


# Called with (phase, processed, total). `processed`/`total` are only meaningful
# during JUDGING_LYRICS (track counts); other phases report (0, 0).
RecommendProgressCallback = Callable[[RecommendPhase, int, int], None]


@dataclass(frozen=True)
class RankedTrack:
    track: PlaylistTrack
    tone: float
    fit: float


@dataclass(frozen=True)
class PlaylistStage:
    name: str
    tracks: list[RankedTrack] = field(default_factory=list)


@dataclass(frozen=True)
class PlaylistRecommendation:
    strategy: Strategy
    signal_probabilities: dict[str, float]
    stages: list[PlaylistStage]
    excluded_no_lyrics: int
    excluded_instrumental: int


class RecommendFromPlaylistUseCase:
    """Judges a prepared playlist's cached lyrics against a mood prompt."""

    def __init__(
        self,
        playlists_client: SpotifyPlaylistsClient,
        lyrics_repository: LyricsRepository,
        judgment_cache: JudgmentCache,
        lyrics_judge: LyricsJudge,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
        tracks_per_stage: int = DEFAULT_TRACKS_PER_STAGE,
        lyrics_truncate_chars: int = DEFAULT_LYRICS_TRUNCATE_CHARS,
    ) -> None:
        self._playlists_client = playlists_client
        self._lyrics_repository = lyrics_repository
        self._judgment_cache = judgment_cache
        self._lyrics_judge = lyrics_judge
        self._max_candidates = max_candidates
        self._tracks_per_stage = tracks_per_stage
        self._lyrics_truncate_chars = lyrics_truncate_chars

    def run(
        self,
        prompt: str,
        playlist_id: str,
        access_token: str,
        on_progress: RecommendProgressCallback | None = None,
    ) -> PlaylistRecommendation:
        def emit(phase: RecommendPhase, processed: int = 0, total: int = 0) -> None:
            if on_progress is not None:
                on_progress(phase, processed, total)

        start = time.perf_counter()
        tracks = self._playlists_client.get_playlist_tracks(playlist_id, access_token)
        entries = [(track, self._lyrics_repository.get(track.id)) for track in tracks]

        if tracks and all(entry is None for _, entry in entries):
            raise PlaylistNotPreparedError(
                f"Playlist {playlist_id} has no cached lyrics yet; call /prepare first."
            )

        usable: list[tuple[PlaylistTrack, str]] = []
        excluded_no_lyrics = 0
        excluded_instrumental = 0
        for track, entry in entries:
            if entry is None or entry.status is LyricsStatus.MISSING:
                excluded_no_lyrics += 1
            elif entry.status is LyricsStatus.INSTRUMENTAL:
                excluded_instrumental += 1
            else:
                usable.append((track, entry.text or ""))

        usable = usable[: self._max_candidates]

        emit(RecommendPhase.DETECTING_MOOD)
        signals, signal_probabilities = self._lyrics_judge.detect_signals(prompt)
        strategy = resolve_playlist_strategy(signals)

        judgments = self._judge_with_cache(prompt, strategy, usable, on_progress=emit)
        ranked = [
            RankedTrack(track=track, tone=judgments[track.id].tone, fit=judgments[track.id].fit)
            for track, _ in usable
        ]

        emit(RecommendPhase.BUILDING_PLAYLIST, len(usable), len(usable))
        if strategy is Strategy.LIFT:
            stages = self._lift_stages(ranked)
        else:
            stages = [self._single_stage(strategy, ranked)]

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "RecommendFromPlaylist playlist=%s strategy=%s candidates=%d judged=%d elapsed_ms=%.0f",
            playlist_id,
            strategy.value,
            len(usable),
            len(judgments),
            elapsed_ms,
        )

        return PlaylistRecommendation(
            strategy=strategy,
            signal_probabilities=signal_probabilities,
            stages=stages,
            excluded_no_lyrics=excluded_no_lyrics,
            excluded_instrumental=excluded_instrumental,
        )

    def _judge_with_cache(
        self,
        prompt: str,
        strategy: Strategy,
        usable: list[tuple[PlaylistTrack, str]],
        on_progress: RecommendProgressCallback | None = None,
    ) -> dict[str, TrackJudgment]:
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        judgments: dict[str, TrackJudgment] = {}
        to_judge: list[tuple[PlaylistTrack, str]] = []
        total = len(usable)
        processed = 0

        def emit_judging() -> None:
            if on_progress is not None:
                on_progress(RecommendPhase.JUDGING_LYRICS, processed, total)

        for track, text in usable:
            tone = self._judgment_cache.get_tone(track.id, QUESTION_SET_VERSION)
            fit = self._judgment_cache.get_fit(track.id, prompt_hash, QUESTION_SET_VERSION)
            if tone is None or fit is None:
                to_judge.append((track, text))
            else:
                judgments[track.id] = TrackJudgment(track_id=track.id, tone=tone, fit=fit)
                processed += 1

        emit_judging()

        if to_judge:
            batch = [
                TrackLyrics(track=track, text=text[: self._lyrics_truncate_chars])
                for track, text in to_judge
            ]

            def on_batch_done(batch_size: int) -> None:
                nonlocal processed
                processed += batch_size
                emit_judging()

            results = self._lyrics_judge.judge_lyrics(prompt, strategy, batch, on_progress=on_batch_done)
            for result in results:
                self._judgment_cache.save_tone(result.track_id, QUESTION_SET_VERSION, result.tone)
                self._judgment_cache.save_fit(
                    result.track_id, prompt_hash, QUESTION_SET_VERSION, result.fit
                )
                judgments[result.track_id] = result

        return judgments

    def _lift_stages(self, ranked: list[RankedTrack]) -> list[PlaylistStage]:
        bands: list[list[RankedTrack]] = [[], [], []]
        for item in ranked:
            for index, (low, high) in enumerate(LIFT_BAND_BOUNDS):
                if low <= item.tone < high:
                    bands[index].append(item)
                    break

        # Borrow from the nearest non-empty band when a band is empty, so a stage is
        # not left without tracks just because no track landed in that tone range.
        for index, band in enumerate(bands):
            if band:
                continue
            for offset in range(1, len(bands)):
                for candidate_index in (index - offset, index + offset):
                    if 0 <= candidate_index < len(bands) and bands[candidate_index]:
                        band.extend(bands[candidate_index])
                        break
                if band:
                    break

        stages = []
        for name, band in zip(LIFT_STAGE_NAMES, bands):
            ranked_band = sorted(band, key=lambda item: item.fit, reverse=True)
            stages.append(PlaylistStage(name=name, tracks=ranked_band[: self._tracks_per_stage]))
        return stages

    def _single_stage(self, strategy: Strategy, ranked: list[RankedTrack]) -> PlaylistStage:
        if strategy is Strategy.ACCOMPANY:
            # Tiebreaker toward the strategy: accompany favors lower (sadder/matching) tone.
            key = lambda item: (-item.fit, item.tone)
        else:
            key = lambda item: -item.fit
        ranked_tracks = sorted(ranked, key=key)
        return PlaylistStage(name=SINGLE_STAGE_NAME, tracks=ranked_tracks)
