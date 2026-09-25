"""Port for the track catalog: finds candidates matching a target audio profile."""

from __future__ import annotations

from typing import Protocol

from mood_dj.domain.models import MoodProfile, Track


class TrackCatalog(Protocol):
    """Looks up candidate tracks close to a target audio profile."""

    def find_candidates(self, profile: MoodProfile, limit: int) -> list[Track]:
        """Return up to `limit` tracks ranked by closeness to the target profile."""
        ...
