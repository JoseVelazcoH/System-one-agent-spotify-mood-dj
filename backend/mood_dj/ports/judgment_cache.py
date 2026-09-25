"""Port for caching Laya lyrics judgments, so repeat runs skip inference.

Tone is a property of the lyrics alone, so it is cached per track. Fit depends on
the listener's prompt too, so it is cached per (track, prompt). Both are also keyed
by a question-set version: changing the question wording bumps the version so stale
judgments made with old wording are not reused silently.
"""

from __future__ import annotations

from typing import Protocol


class JudgmentCache(Protocol):
    def get_tone(self, track_id: str, question_version: str) -> float | None: ...

    def save_tone(self, track_id: str, question_version: str, tone: float) -> None: ...

    def get_fit(self, track_id: str, prompt_hash: str, question_version: str) -> float | None: ...

    def save_fit(self, track_id: str, prompt_hash: str, question_version: str, fit: float) -> None: ...
