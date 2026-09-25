"""Unit tests for the deterministic playlist-mode strategy mapping.

`resolve_playlist_strategy` maps four independent noul signals (feels_bad,
wants_change, wants_energy, wants_rest) to a `Strategy`, per the documented
decision table:

    feels_bad & wants_change      -> lift
    feels_bad & not wants_change  -> accompany
    wants_energy                  -> energize
    wants_rest                    -> calm
    (default, none of the above)  -> accompany
"""

from __future__ import annotations

from mood_dj.domain.models import Strategy
from mood_dj.domain.playlist_strategy import PlaylistSignals, resolve_playlist_strategy


def _signals(**overrides: bool) -> PlaylistSignals:
    defaults = dict(feels_bad=False, wants_change=False, wants_energy=False, wants_rest=False)
    defaults.update(overrides)
    return PlaylistSignals(**defaults)


def test_feels_bad_and_wants_change_lifts_mood():
    assert resolve_playlist_strategy(_signals(feels_bad=True, wants_change=True)) == Strategy.LIFT


def test_feels_bad_without_wanting_change_accompanies():
    assert (
        resolve_playlist_strategy(_signals(feels_bad=True, wants_change=False))
        == Strategy.ACCOMPANY
    )


def test_wants_energy_energizes_even_when_feeling_bad():
    assert (
        resolve_playlist_strategy(_signals(feels_bad=True, wants_energy=True)) == Strategy.ENERGIZE
    )


def test_wants_rest_calms_when_not_feeling_bad():
    assert resolve_playlist_strategy(_signals(wants_rest=True)) == Strategy.CALM


def test_no_signals_defaults_to_accompany():
    assert resolve_playlist_strategy(_signals()) == Strategy.ACCOMPANY


def test_wants_energy_takes_priority_over_wants_rest():
    assert (
        resolve_playlist_strategy(_signals(wants_energy=True, wants_rest=True))
        == Strategy.ENERGIZE
    )
