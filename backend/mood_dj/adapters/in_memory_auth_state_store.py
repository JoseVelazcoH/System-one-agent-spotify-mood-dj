"""AuthStateStore adapter backed by an in-process dict.

Pending auth attempts are short-lived (the user completes the Spotify consent
screen within a few minutes), so process memory is sufficient; no persistence is
needed across server restarts.
"""

from __future__ import annotations

import threading


class InMemoryAuthStateStore:
    """Stores PKCE code verifiers per OAuth `state`, guarded by a lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._verifiers: dict[str, str] = {}

    def save(self, state: str, code_verifier: str) -> None:
        with self._lock:
            self._verifiers[state] = code_verifier

    def pop(self, state: str) -> str | None:
        with self._lock:
            return self._verifiers.pop(state, None)
