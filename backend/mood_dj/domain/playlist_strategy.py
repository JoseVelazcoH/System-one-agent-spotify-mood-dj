"""Deterministic strategy mapping for the "My playlists" mode.

Instead of a single 4-way choice question (which in practice kept collapsing to
"calm"), the playlist mode asks Laya four independent noul (yes/no) questions
about the prompt and maps the answers to a `Strategy` with a plain decision
table. This module is pure and framework-free so it can be unit tested without
touching the model or the network.
"""

from __future__ import annotations

from dataclasses import dataclass

from mood_dj.domain.models import Strategy


@dataclass(frozen=True)
class PlaylistSignals:
    """Boolean signals derived from thresholding Laya's noul probabilities."""

    feels_bad: bool
    wants_change: bool
    wants_energy: bool
    wants_rest: bool


def resolve_playlist_strategy(signals: PlaylistSignals) -> Strategy:
    """Map prompt signals to a listening strategy.

    Priority order: wants_energy beats everything else (an explicit request for
    energy or movement should not be muted by also feeling bad or wanting rest).
    Then feels_bad decides between lift (wants change) and accompany (does not).
    Then wants_rest maps to calm. Anything left over defaults to accompany.
    """
    if signals.wants_energy:
        return Strategy.ENERGIZE
    if signals.feels_bad:
        return Strategy.LIFT if signals.wants_change else Strategy.ACCOMPANY
    if signals.wants_rest:
        return Strategy.CALM
    return Strategy.ACCOMPANY
