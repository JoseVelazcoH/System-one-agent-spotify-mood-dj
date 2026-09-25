"""Unit tests for RecommendFromPlaylistUseCase, using fake adapters (no network, no model)."""

from __future__ import annotations

import pytest

from mood_dj.application.recommend_from_playlist import (
    PlaylistNotPreparedError,
    RecommendFromPlaylistUseCase,
    RecommendPhase,
)
from mood_dj.domain.models import LyricsEntry, LyricsStatus, PlaylistTrack, Strategy
from mood_dj.domain.playlist_strategy import PlaylistSignals
from mood_dj.ports.lyrics_judge import TrackJudgment


def _track(track_id: str) -> PlaylistTrack:
    return PlaylistTrack(
        id=track_id,
        name=f"Song {track_id}",
        artist="Artist",
        album="Album",
        duration_s=200.0,
        cover_url=f"https://covers.example/{track_id}.jpg",
        external_url=f"https://open.spotify.com/track/{track_id}",
    )


class FakePlaylistsClient:
    def __init__(self, tracks: list[PlaylistTrack]) -> None:
        self.tracks = tracks

    def list_playlists(self, access_token: str):
        return []

    def get_playlist_tracks(self, playlist_id: str, access_token: str):
        return self.tracks


class FakeLyricsRepository:
    def __init__(self, entries: dict[str, LyricsEntry]) -> None:
        self.entries = entries

    def get(self, track_id: str):
        return self.entries.get(track_id)

    def save(self, entry: LyricsEntry) -> None:
        self.entries[entry.track_id] = entry


class FakeJudgmentCache:
    def __init__(self) -> None:
        self.tones: dict[tuple[str, str], float] = {}
        self.fits: dict[tuple[str, str, str], float] = {}

    def get_tone(self, track_id, question_version):
        return self.tones.get((track_id, question_version))

    def save_tone(self, track_id, question_version, tone):
        self.tones[(track_id, question_version)] = tone

    def get_fit(self, track_id, prompt_hash, question_version):
        return self.fits.get((track_id, prompt_hash, question_version))

    def save_fit(self, track_id, prompt_hash, question_version, fit):
        self.fits[(track_id, prompt_hash, question_version)] = fit


class FakeLyricsJudge:
    def __init__(self, strategy_signals: PlaylistSignals, tones: dict[str, float], fits: dict[str, float]) -> None:
        self.strategy_signals = strategy_signals
        self.tones = tones
        self.fits = fits
        self.judge_calls = 0
        self.judged_track_ids: list[str] = []

    def detect_signals(self, prompt: str):
        return self.strategy_signals, {"feels_bad": 1.0, "wants_change": 1.0, "wants_energy": 0.0, "wants_rest": 0.0}

    def judge_lyrics(self, prompt, strategy, tracks, on_progress=None):
        self.judge_calls += 1
        results = []
        for item in tracks:
            self.judged_track_ids.append(item.track.id)
            results.append(
                TrackJudgment(
                    track_id=item.track.id,
                    tone=self.tones[item.track.id],
                    fit=self.fits[item.track.id],
                )
            )
        if on_progress is not None and tracks:
            on_progress(len(tracks))
        return results


def _entry(track_id: str, status: LyricsStatus, text: str | None = "la la la") -> LyricsEntry:
    return LyricsEntry(track_id=track_id, status=status, text=text, fetched_at="2026-09-25T00:00:00+00:00")


LIFT_SIGNALS = PlaylistSignals(feels_bad=True, wants_change=True, wants_energy=False, wants_rest=False)
ACCOMPANY_SIGNALS = PlaylistSignals(feels_bad=True, wants_change=False, wants_energy=False, wants_rest=False)


def test_raises_when_playlist_was_never_prepared() -> None:
    tracks = [_track("1"), _track("2")]
    use_case = RecommendFromPlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks),
        lyrics_repository=FakeLyricsRepository({}),
        judgment_cache=FakeJudgmentCache(),
        lyrics_judge=FakeLyricsJudge(LIFT_SIGNALS, {}, {}),
    )

    with pytest.raises(PlaylistNotPreparedError):
        use_case.run("I feel sad", "playlist-1", "token")


def test_excludes_tracks_without_lyrics_and_instrumentals() -> None:
    tracks = [_track("has-lyrics"), _track("missing"), _track("instrumental")]
    entries = {
        "has-lyrics": _entry("has-lyrics", LyricsStatus.LYRICS),
        "missing": _entry("missing", LyricsStatus.MISSING, text=None),
        "instrumental": _entry("instrumental", LyricsStatus.INSTRUMENTAL, text=None),
    }
    judge = FakeLyricsJudge(ACCOMPANY_SIGNALS, {"has-lyrics": 0.5}, {"has-lyrics": 0.9})
    use_case = RecommendFromPlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks),
        lyrics_repository=FakeLyricsRepository(entries),
        judgment_cache=FakeJudgmentCache(),
        lyrics_judge=judge,
    )

    result = use_case.run("I feel sad", "playlist-1", "token")

    assert result.excluded_no_lyrics == 1
    assert result.excluded_instrumental == 1
    all_tracks = [t for stage in result.stages for t in stage.tracks]
    assert [t.track.id for t in all_tracks] == ["has-lyrics"]


def test_lift_strategy_produces_three_tone_ordered_stages() -> None:
    ids = [f"t{i}" for i in range(6)]
    tracks = [_track(tid) for tid in ids]
    entries = {tid: _entry(tid, LyricsStatus.LYRICS) for tid in ids}
    tones = {"t0": 0.05, "t1": 0.1, "t2": 0.5, "t3": 0.55, "t4": 0.9, "t5": 0.95}
    fits = {tid: 0.8 for tid in ids}
    judge = FakeLyricsJudge(LIFT_SIGNALS, tones, fits)
    use_case = RecommendFromPlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks),
        lyrics_repository=FakeLyricsRepository(entries),
        judgment_cache=FakeJudgmentCache(),
        lyrics_judge=judge,
    )

    result = use_case.run("Estoy triste pero quiero sentirme mejor", "playlist-1", "token")

    assert result.strategy is Strategy.LIFT
    assert [s.name for s in result.stages] == ["melancholic", "hopeful", "positive"]
    assert {t.track.id for t in result.stages[0].tracks} == {"t0", "t1"}
    assert {t.track.id for t in result.stages[1].tracks} == {"t2", "t3"}
    assert {t.track.id for t in result.stages[2].tracks} == {"t4", "t5"}


def test_single_stage_ranked_by_fit_for_non_lift_strategy() -> None:
    ids = ["low-fit", "high-fit"]
    tracks = [_track(tid) for tid in ids]
    entries = {tid: _entry(tid, LyricsStatus.LYRICS) for tid in ids}
    judge = FakeLyricsJudge(
        ACCOMPANY_SIGNALS, tones={"low-fit": 0.5, "high-fit": 0.5}, fits={"low-fit": 0.1, "high-fit": 0.9}
    )
    use_case = RecommendFromPlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks),
        lyrics_repository=FakeLyricsRepository(entries),
        judgment_cache=FakeJudgmentCache(),
        lyrics_judge=judge,
    )

    result = use_case.run("I want music that matches how I feel", "playlist-1", "token")

    assert len(result.stages) == 1
    assert [t.track.id for t in result.stages[0].tracks] == ["high-fit", "low-fit"]


def test_cached_judgments_are_not_rejudged() -> None:
    tracks = [_track("t1")]
    entries = {"t1": _entry("t1", LyricsStatus.LYRICS)}
    cache = FakeJudgmentCache()
    cache.save_tone("t1", "v1", 0.5)
    import hashlib

    prompt = "same prompt"
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    cache.save_fit("t1", prompt_hash, "v1", 0.7)
    judge = FakeLyricsJudge(ACCOMPANY_SIGNALS, {}, {})
    use_case = RecommendFromPlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks),
        lyrics_repository=FakeLyricsRepository(entries),
        judgment_cache=cache,
        lyrics_judge=judge,
    )

    result = use_case.run(prompt, "playlist-1", "token")

    assert judge.judge_calls == 0
    assert result.stages[0].tracks[0].tone == 0.5
    assert result.stages[0].tracks[0].fit == 0.7


def test_max_candidates_limits_judged_tracks() -> None:
    ids = [f"t{i}" for i in range(10)]
    tracks = [_track(tid) for tid in ids]
    entries = {tid: _entry(tid, LyricsStatus.LYRICS) for tid in ids}
    judge = FakeLyricsJudge(ACCOMPANY_SIGNALS, {tid: 0.5 for tid in ids}, {tid: 0.5 for tid in ids})
    use_case = RecommendFromPlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks),
        lyrics_repository=FakeLyricsRepository(entries),
        judgment_cache=FakeJudgmentCache(),
        lyrics_judge=judge,
        max_candidates=3,
    )

    result = use_case.run("prompt", "playlist-1", "token")

    total_tracks = sum(len(stage.tracks) for stage in result.stages)
    assert total_tracks == 3


def test_reports_progress_through_all_phases() -> None:
    tracks = [_track("cached"), _track("fresh")]
    entries = {tid: _entry(tid, LyricsStatus.LYRICS) for tid in ["cached", "fresh"]}
    cache = FakeJudgmentCache()
    cache.save_tone("cached", "v1", 0.5)
    import hashlib

    prompt = "prompt"
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    cache.save_fit("cached", prompt_hash, "v1", 0.7)
    judge = FakeLyricsJudge(ACCOMPANY_SIGNALS, {"fresh": 0.5}, {"fresh": 0.5})
    use_case = RecommendFromPlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks),
        lyrics_repository=FakeLyricsRepository(entries),
        judgment_cache=cache,
        lyrics_judge=judge,
    )
    calls: list[tuple[RecommendPhase, int, int]] = []

    use_case.run(prompt, "playlist-1", "token", on_progress=lambda phase, processed, total: calls.append((phase, processed, total)))

    phases = [call[0] for call in calls]
    assert phases[0] is RecommendPhase.DETECTING_MOOD
    assert RecommendPhase.JUDGING_LYRICS in phases
    assert phases[-1] is RecommendPhase.BUILDING_PLAYLIST
    judging_calls = [call for call in calls if call[0] is RecommendPhase.JUDGING_LYRICS]
    # First judging_lyrics call already counts the cache hit; the last one counts both.
    assert judging_calls[0][1] == 1
    assert judging_calls[0][2] == 2
    assert judging_calls[-1][1] == 2
