"""Port for reading a user's playlists and playlist tracks from Spotify."""

from __future__ import annotations

from typing import Protocol

from mood_dj.domain.models import PlaylistSummary, PlaylistTrack


class SpotifyPlaylistsClient(Protocol):
    """Reads playlists and playlist tracks on behalf of an authenticated user."""

    def list_playlists(self, access_token: str) -> list[PlaylistSummary]:
        """Return all of the user's playlists, following pagination."""
        ...

    def get_playlist_tracks(self, playlist_id: str, access_token: str) -> list[PlaylistTrack]:
        """Return all tracks in a playlist, following pagination."""
        ...
