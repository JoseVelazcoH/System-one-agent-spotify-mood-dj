"""Unit tests for the PreparePlaylist application use case, using in-memory fakes."""

from __future__ import annotations

import threading

from mood_dj.application.prepare_playlist import PreparePlaylistUseCase
from mood_dj.domain.models import LyricsEntry, LyricsStatus, PlaylistTrack, PrepareState
from mood_dj.ports.lyrics_provider import LyricsLookupResult


def _track(track_id: str) -> PlaylistTrack:
    return PlaylistTrack(
        id=track_id,
        name=f"Song {track_id}",
        artist="Artist",
        album="Album",
        duration_s=200.0,
        cover_url=None,
        external_url=None,
    )


class FakePlaylistsClient:
    def __init__(self, tracks: list[PlaylistTrack]) -> None:
        self.tracks = tracks

    def get_playlist_tracks(self, playlist_id: str, access_token: str) -> list[PlaylistTrack]:
        return self.tracks


class FakeLyricsRepository:
    def __init__(self, existing: dict[str, LyricsEntry] | None = None) -> None:
        self._store = dict(existing or {})
        self.saved: list[LyricsEntry] = []

    def get(self, track_id: str) -> LyricsEntry | None:
        return self._store.get(track_id)

    def save(self, entry: LyricsEntry) -> None:
        self._store[entry.track_id] = entry
        self.saved.append(entry)


class FakeLyricsProvider:
    def __init__(self, results: dict[str, LyricsLookupResult]) -> None:
        self.results = results
        self.calls: list[str] = []
        self.lock = threading.Lock()

    def fetch(self, artist: str, title: str, album: str, duration_s: float) -> LyricsLookupResult:
        with self.lock:
            self.calls.append(title)
        # title == "Song {track_id}" in this test's fixture
        track_id = title.split(" ")[-1]
        return self.results[track_id]


def test_run_fetches_lyrics_only_for_tracks_missing_from_repository() -> None:
    tracks = [_track("t1"), _track("t2")]
    repo = FakeLyricsRepository(
        existing={"t1": LyricsEntry(track_id="t1", status=LyricsStatus.LYRICS, text="x", fetched_at="now")}
    )
    provider = FakeLyricsProvider({"t2": LyricsLookupResult(status=LyricsStatus.MISSING)})
    use_case = PreparePlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks), lyrics_repository=repo, lyrics_provider=provider
    )

    progress = use_case.run("playlist-1", "token")

    assert provider.calls == ["Song t2"]
    assert progress.total == 2
    assert progress.processed == 2
    assert progress.with_lyrics == 1
    assert progress.missing == 1


def test_run_stores_only_definitive_results_not_network_errors() -> None:
    tracks = [_track("t1")]
    repo = FakeLyricsRepository()
    provider = FakeLyricsProvider({"t1": LyricsLookupResult(status=None)})
    use_case = PreparePlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks), lyrics_repository=repo, lyrics_provider=provider
    )

    progress = use_case.run("playlist-1", "token")

    assert repo.saved == []
    assert progress.processed == 1
    assert progress.missing == 0
    assert progress.with_lyrics == 0
    assert progress.instrumental == 0


def test_run_counts_instrumental_tracks() -> None:
    tracks = [_track("t1")]
    repo = FakeLyricsRepository()
    provider = FakeLyricsProvider({"t1": LyricsLookupResult(status=LyricsStatus.INSTRUMENTAL)})
    use_case = PreparePlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks), lyrics_repository=repo, lyrics_provider=provider
    )

    progress = use_case.run("playlist-1", "token")

    assert progress.instrumental == 1
    assert repo.saved[0].status is LyricsStatus.INSTRUMENTAL


def test_run_reports_progress_via_callback() -> None:
    tracks = [_track("t1"), _track("t2"), _track("t3")]
    repo = FakeLyricsRepository()
    provider = FakeLyricsProvider({tid: LyricsLookupResult(status=LyricsStatus.MISSING) for tid in ["t1", "t2", "t3"]})
    use_case = PreparePlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks), lyrics_repository=repo, lyrics_provider=provider
    )
    seen_totals = []

    def on_progress(progress):
        seen_totals.append((progress.total, progress.processed))

    final = use_case.run("playlist-1", "token", on_progress=on_progress)

    assert final.processed == 3
    assert seen_totals[-1] == (3, 3)


def test_run_uses_bounded_concurrency() -> None:
    tracks = [_track(f"t{i}") for i in range(20)]
    repo = FakeLyricsRepository()
    provider = FakeLyricsProvider({f"t{i}": LyricsLookupResult(status=LyricsStatus.MISSING) for i in range(20)})
    use_case = PreparePlaylistUseCase(
        playlists_client=FakePlaylistsClient(tracks),
        lyrics_repository=repo,
        lyrics_provider=provider,
        max_concurrency=6,
    )

    progress = use_case.run("playlist-1", "token")

    assert progress.processed == 20
    assert len(provider.calls) == 20
