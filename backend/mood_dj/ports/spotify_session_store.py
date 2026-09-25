"""Port for persisting Spotify user OAuth sessions, keyed by an app session id."""

from __future__ import annotations

from typing import Protocol

from mood_dj.domain.models import SpotifyTokens


class SpotifySessionStore(Protocol):
    """Stores and retrieves Spotify OAuth tokens per app session id."""

    def save(self, session_id: str, tokens: SpotifyTokens) -> None:
        """Persist (insert or replace) the tokens for a session."""
        ...

    def get(self, session_id: str) -> SpotifyTokens | None:
        """Return the tokens for a session, or None if there is no such session."""
        ...

    def delete(self, session_id: str) -> None:
        """Remove a session's tokens, if any."""
        ...
