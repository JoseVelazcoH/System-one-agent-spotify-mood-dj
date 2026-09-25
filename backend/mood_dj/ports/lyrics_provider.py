"""Port for looking up lyrics for a track from an external lyrics source."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mood_dj.domain.models import LyricsStatus


@dataclass(frozen=True)
class LyricsLookupResult:
    """The outcome of a single lyrics lookup attempt.

    `status` is None when the lookup failed for a transient reason (network error,
    unexpected server error): the caller should not cache this result, so the track
    is retried on the next preparation run. A definitive "no lyrics found" answer is
    represented as `LyricsStatus.MISSING`, which is safe to cache.
    """

    status: LyricsStatus | None
    text: str | None = None


class LyricsProvider(Protocol):
    """Looks up lyrics for a track by artist, title, album and duration."""

    def fetch(self, artist: str, title: str, album: str, duration_s: float) -> LyricsLookupResult:
        """Look up lyrics for a single track."""
        ...
