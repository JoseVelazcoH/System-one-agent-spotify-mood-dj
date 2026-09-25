"""FastAPI dependency wiring for auth and playlist endpoints."""

from __future__ import annotations

import time
from functools import lru_cache

from fastapi import Cookie, Depends, HTTPException

from mood_dj.adapters.in_memory_auth_state_store import InMemoryAuthStateStore
from mood_dj.adapters.laya_lyrics_judge import LayaLyricsJudge
from mood_dj.adapters.lrclib_lyrics import LrclibLyricsProvider
from mood_dj.adapters.sqlite_judgment_cache import SqliteJudgmentCache
from mood_dj.adapters.sqlite_lyrics_repository import SqliteLyricsRepository
from mood_dj.adapters.sqlite_session_store import SqliteSessionStore
from mood_dj.adapters.spotify_auth import SpotifyAuthClient
from mood_dj.adapters.spotify_playlists import SpotifyPlaylistsClient
from mood_dj.application.prepare_job_manager import PrepareJobManager
from mood_dj.application.prepare_playlist import PreparePlaylistUseCase
from mood_dj.application.recommend_from_playlist import RecommendFromPlaylistUseCase
from mood_dj.config import Settings, load_settings
from mood_dj.domain.models import SpotifyTokens
from mood_dj.ports.auth_state_store import AuthStateStore
from mood_dj.ports.judgment_cache import JudgmentCache
from mood_dj.ports.lyrics_judge import LyricsJudge
from mood_dj.ports.lyrics_provider import LyricsProvider
from mood_dj.ports.lyrics_repository import LyricsRepository
from mood_dj.ports.spotify_playlists import SpotifyPlaylistsClient as SpotifyPlaylistsClientPort
from mood_dj.ports.spotify_session_store import SpotifySessionStore

TOKEN_REFRESH_MARGIN_S = 30


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


@lru_cache(maxsize=1)
def get_auth_state_store() -> AuthStateStore:
    return InMemoryAuthStateStore()


@lru_cache(maxsize=1)
def get_session_store() -> SpotifySessionStore:
    return SqliteSessionStore(get_settings().app_db_path)


@lru_cache(maxsize=1)
def get_lyrics_repository() -> LyricsRepository:
    return SqliteLyricsRepository(get_settings().app_db_path)


@lru_cache(maxsize=1)
def get_auth_client() -> SpotifyAuthClient:
    return SpotifyAuthClient(client_id=get_settings().spotify_client_id)


@lru_cache(maxsize=1)
def get_playlists_client() -> SpotifyPlaylistsClientPort:
    return SpotifyPlaylistsClient()


@lru_cache(maxsize=1)
def get_lyrics_provider() -> LyricsProvider:
    return LrclibLyricsProvider()


@lru_cache(maxsize=1)
def get_job_manager() -> PrepareJobManager:
    def factory() -> PreparePlaylistUseCase:
        return PreparePlaylistUseCase(
            playlists_client=get_playlists_client(),
            lyrics_repository=get_lyrics_repository(),
            lyrics_provider=get_lyrics_provider(),
        )

    return PrepareJobManager(use_case_factory=factory)


@lru_cache(maxsize=1)
def get_judgment_cache() -> JudgmentCache:
    return SqliteJudgmentCache(get_settings().app_db_path)


@lru_cache(maxsize=1)
def get_lyrics_judge() -> LyricsJudge:
    # lru_cache ensures the Laya Router (and its loaded checkpoints) is built once
    # and shared across requests instead of being reloaded per call.
    return LayaLyricsJudge()


@lru_cache(maxsize=1)
def get_recommend_from_playlist_use_case() -> RecommendFromPlaylistUseCase:
    return RecommendFromPlaylistUseCase(
        playlists_client=get_playlists_client(),
        lyrics_repository=get_lyrics_repository(),
        judgment_cache=get_judgment_cache(),
        lyrics_judge=get_lyrics_judge(),
    )


def get_session_id(session_id: str | None = Cookie(default=None)) -> str:
    if session_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return session_id


def get_current_tokens(
    session_id: str = Depends(get_session_id),
    session_store: SpotifySessionStore = Depends(get_session_store),
    auth_client: SpotifyAuthClient = Depends(get_auth_client),
) -> SpotifyTokens:
    tokens = session_store.get(session_id)
    if tokens is None:
        raise HTTPException(status_code=401, detail="Not logged in")

    if tokens.expires_at <= time.time() + TOKEN_REFRESH_MARGIN_S:
        tokens = auth_client.refresh(tokens.refresh_token)
        session_store.save(session_id, tokens)

    return tokens
