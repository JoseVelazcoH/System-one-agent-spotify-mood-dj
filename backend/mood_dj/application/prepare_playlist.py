"""Use case: fetch lyrics for every track in a playlist not yet cached."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable

from mood_dj.domain.models import LyricsEntry, PlaylistTrack, PrepareProgress, PrepareState
from mood_dj.ports.lyrics_provider import LyricsProvider
from mood_dj.ports.lyrics_repository import LyricsRepository
from mood_dj.ports.spotify_playlists import SpotifyPlaylistsClient

DEFAULT_MAX_CONCURRENCY = 6

ProgressCallback = Callable[[PrepareProgress], None]


class PreparePlaylistUseCase:
    """Loads a playlist's tracks and fills in missing lyrics lookups.

    Tracks already present in the lyrics repository are skipped. Lookups for the
    remaining tracks run with bounded concurrency, since LRCLIB is a shared public
    service and this keeps request load reasonable.
    """

    def __init__(
        self,
        playlists_client: SpotifyPlaylistsClient,
        lyrics_repository: LyricsRepository,
        lyrics_provider: LyricsProvider,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        self._playlists_client = playlists_client
        self._lyrics_repository = lyrics_repository
        self._lyrics_provider = lyrics_provider
        self._max_concurrency = max_concurrency

    def run(
        self,
        playlist_id: str,
        access_token: str,
        on_progress: ProgressCallback | None = None,
    ) -> PrepareProgress:
        tracks = self._playlists_client.get_playlist_tracks(playlist_id, access_token)
        progress = PrepareProgress(state=PrepareState.RUNNING, total=len(tracks))
        lock = threading.Lock()

        def emit() -> None:
            if on_progress is not None:
                on_progress(progress)

        emit()

        pending: list[PlaylistTrack] = []
        for track in tracks:
            cached = self._lyrics_repository.get(track.id)
            if cached is None:
                pending.append(track)
            else:
                with lock:
                    self._count_status(cached.status.value, progress)
                    progress.processed += 1
        if len(pending) != len(tracks):
            emit()

        def process(track: PlaylistTrack) -> None:
            self._process_track(track, progress, lock)
            emit()

        if pending:
            with ThreadPoolExecutor(max_workers=self._max_concurrency) as executor:
                list(executor.map(process, pending))

        progress.state = PrepareState.DONE
        emit()
        return progress

    def _process_track(self, track: PlaylistTrack, progress: PrepareProgress, lock: threading.Lock) -> None:
        result = self._lyrics_provider.fetch(track.artist, track.name, track.album, track.duration_s)
        if result.status is not None:
            entry = LyricsEntry(
                track_id=track.id,
                status=result.status,
                text=result.text,
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )
            self._lyrics_repository.save(entry)

        with lock:
            progress.processed += 1
            if result.status is not None:
                self._count_status(result.status.value, progress)

    def _count_status(self, status_value: str, progress: PrepareProgress) -> None:
        if status_value == "lyrics":
            progress.with_lyrics += 1
        elif status_value == "instrumental":
            progress.instrumental += 1
        elif status_value == "missing":
            progress.missing += 1
