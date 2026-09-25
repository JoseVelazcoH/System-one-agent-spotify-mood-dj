"""Port for storing pending Spotify PKCE auth attempts, keyed by OAuth `state`."""

from __future__ import annotations

from typing import Protocol


class AuthStateStore(Protocol):
    """Stores the PKCE code verifier for an in-flight `/auth/login` attempt."""

    def save(self, state: str, code_verifier: str) -> None:
        """Remember the code verifier generated for this `state` value."""
        ...

    def pop(self, state: str) -> str | None:
        """Return and remove the code verifier for `state`, or None if unknown/used."""
        ...
