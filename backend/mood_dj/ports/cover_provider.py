"""Port for enriching tracks with cover art and external links."""

from __future__ import annotations

from typing import Protocol

from mood_dj.domain.models import Track


class CoverProvider(Protocol):
    """Enriches tracks with cover image URL and external listen link."""

    def enrich(self, tracks: list[Track]) -> list[Track]:
        """Return a new list of tracks with cover_url and external_url filled in."""
        ...
