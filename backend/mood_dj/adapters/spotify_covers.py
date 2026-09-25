"""CoverProvider adapter backed by the Spotify Web API.

Uses the Client Credentials flow (app-only auth) and the single-track endpoint
`GET /v1/tracks/{id}`, requested concurrently. The batch endpoint `GET /v1/tracks?ids=`
answers 403 for this app tier while the single-track one works, so it is not used. `audio-features` and `recommendations` return 403 for new Spotify apps since
November 2024, so this adapter never calls them; audio features come from the
DuckDB-backed dataset catalog instead.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

import httpx

from mood_dj.domain.models import Track

logger = logging.getLogger(__name__)

MAX_CONCURRENT_REQUESTS = 8
TOKEN_URL = "https://accounts.spotify.com/api/token"
TRACKS_URL = "https://api.spotify.com/v1/tracks"


class SpotifyHttpClient(Protocol):
    """Thin boundary around the two Spotify HTTP calls this adapter needs."""

    def post_token(self, client_id: str, client_secret: str) -> str:
        """Exchange client credentials for an access token."""
        ...

    def get_track(self, track_id: str, access_token: str) -> dict | None:
        """Fetch metadata for one track, or None when Spotify does not know it."""
        ...


class HttpxSpotifyHttpClient:
    """Real Spotify HTTP client, built on httpx."""

    def post_token(self, client_id: str, client_secret: str) -> str:
        response = httpx.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def get_track(self, track_id: str, access_token: str) -> dict | None:
        response = httpx.get(
            f"{TRACKS_URL}/{track_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        response.raise_for_status()
        return response.json()


class SpotifyCoverProvider:
    """Enriches tracks with cover art and external URL from the Spotify catalog."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        http_client: SpotifyHttpClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._http_client = http_client or HttpxSpotifyHttpClient()

    def enrich(self, tracks: list[Track]) -> list[Track]:
        if not tracks:
            return []

        access_token = self._http_client.post_token(self._client_id, self._client_secret)
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
            metadata = executor.map(lambda track: self._fetch(track.id, access_token), tracks)
            return [self._merge(track, entry) for track, entry in zip(tracks, metadata)]

    def _fetch(self, track_id: str, access_token: str) -> dict | None:
        # A missing cover must not break the whole playlist, so failures degrade to None.
        try:
            return self._http_client.get_track(track_id, access_token)
        except Exception:
            logger.warning("Could not fetch Spotify metadata for track %s", track_id, exc_info=True)
            return None

    def _merge(self, track: Track, metadata: dict | None) -> Track:
        if metadata is None:
            return track
        images = metadata.get("album", {}).get("images", [])
        cover_url = images[0]["url"] if images else None
        external_url = metadata.get("external_urls", {}).get("spotify")
        return Track(**{**track.__dict__, "cover_url": cover_url, "external_url": external_url})
