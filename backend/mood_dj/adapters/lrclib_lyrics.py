"""LyricsProvider adapter backed by the LRCLIB API (https://lrclib.net).

Tries an exact match first via `GET /api/get` (artist, track, album, duration).
On a 404, falls back to `GET /api/search` with a cleaned track title, since LRCLIB's
exact match is strict about title suffixes like "- Remastered 2011" that Spotify
commonly appends but the underlying recording's lyrics entry does not carry.

Network errors are reported as `LyricsLookupResult(status=None)` so the caller does
not cache them: the track is retried on a later preparation run.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

import httpx

from mood_dj.domain.models import LyricsStatus
from mood_dj.ports.lyrics_provider import LyricsLookupResult

logger = logging.getLogger(__name__)

GET_URL = "https://lrclib.net/api/get"
SEARCH_URL = "https://lrclib.net/api/search"
USER_AGENT = "laya-spotify/0.1.0 (https://github.com/laya-spotify; playlist lyrics lookup)"
REQUEST_TIMEOUT = 10.0

_TITLE_SUFFIX_PATTERNS = [
    r"\s*\(feat\.[^)]*\)",
    r"\s*\[[^\]]*\]",
    r"\s*-\s*Remaster(?:ed|izado)?(?:\s+\d{4})?",
    r"\s*-\s*Live(?:\s+.*)?",
    r"\s*-\s*Acoustic(?:\s+Version)?",
]
_TITLE_SUFFIX_RE = re.compile("|".join(_TITLE_SUFFIX_PATTERNS), re.IGNORECASE)


def clean_title(title: str) -> str:
    """Strip common Spotify title suffixes that break LRCLIB's exact match."""
    cleaned = _TITLE_SUFFIX_RE.sub("", title)
    return cleaned.strip()


class LrclibHttpClient(Protocol):
    """Thin boundary around the two LRCLIB HTTP calls this adapter needs."""

    def get(self, params: dict) -> dict:
        """Call `/api/get`. Raises `httpx.HTTPStatusError` on 404."""
        ...

    def search(self, params: dict):
        """Call `/api/search`. Returns a list of matches, or an error object."""
        ...


class HttpxLrclibHttpClient:
    """Real LRCLIB HTTP client, built on httpx."""

    def get(self, params: dict) -> dict:
        response = httpx.get(
            GET_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()

    def search(self, params: dict):
        response = httpx.get(
            SEARCH_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()


class LrclibLyricsProvider:
    """Looks up lyrics on LRCLIB, with a cleaned-title search fallback."""

    def __init__(self, http_client: LrclibHttpClient | None = None) -> None:
        self._http_client = http_client or HttpxLrclibHttpClient()

    def fetch(self, artist: str, title: str, album: str, duration_s: float) -> LyricsLookupResult:
        try:
            payload = self._http_client.get(
                {
                    "artist_name": artist,
                    "track_name": title,
                    "album_name": album,
                    "duration": int(duration_s),
                }
            )
            return self._result_from_payload(payload)
        except httpx.HTTPStatusError as error:
            if error.response.status_code != httpx.codes.NOT_FOUND:
                logger.warning("LRCLIB /api/get failed for %r - %r", artist, title, exc_info=True)
                return LyricsLookupResult(status=None)
        except httpx.HTTPError:
            logger.warning("LRCLIB /api/get network error for %r - %r", artist, title, exc_info=True)
            return LyricsLookupResult(status=None)

        return self._search_fallback(artist, title)

    def _search_fallback(self, artist: str, title: str) -> LyricsLookupResult:
        try:
            matches = self._http_client.search({"track_name": clean_title(title), "artist_name": artist})
        except httpx.HTTPError:
            logger.warning("LRCLIB /api/search network error for %r - %r", artist, title, exc_info=True)
            return LyricsLookupResult(status=None)

        if not isinstance(matches, list) or not matches:
            return LyricsLookupResult(status=LyricsStatus.MISSING)

        return self._result_from_payload(matches[0])

    def _result_from_payload(self, payload: dict) -> LyricsLookupResult:
        if payload.get("instrumental"):
            return LyricsLookupResult(status=LyricsStatus.INSTRUMENTAL, text=None)
        text = payload.get("plainLyrics")
        if not text:
            return LyricsLookupResult(status=LyricsStatus.MISSING)
        return LyricsLookupResult(status=LyricsStatus.LYRICS, text=text)
