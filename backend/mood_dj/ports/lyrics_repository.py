"""Port for persisting lyrics lookup results, keyed by Spotify track id."""

from __future__ import annotations

from typing import Protocol

from mood_dj.domain.models import LyricsEntry


class LyricsRepository(Protocol):
    """Stores and retrieves cached lyrics lookup results."""

    def get(self, track_id: str) -> LyricsEntry | None:
        """Return the cached entry for a track, or None if never looked up."""
        ...

    def save(self, entry: LyricsEntry) -> None:
        """Persist (insert or replace) a lyrics lookup result."""
        ...
