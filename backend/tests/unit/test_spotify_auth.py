"""Unit tests for the Spotify PKCE auth adapter, using a fake HTTP client."""

from __future__ import annotations

import base64
import hashlib

from mood_dj.adapters.spotify_auth import (
    SpotifyAuthClient,
    build_authorize_url,
    generate_code_verifier,
    generate_state,
)


def test_generate_code_verifier_has_valid_length_and_charset() -> None:
    verifier = generate_code_verifier()

    assert 43 <= len(verifier) <= 128
    assert all(c.isalnum() or c in "-._~" for c in verifier)


def test_generate_code_verifier_is_unique_per_call() -> None:
    assert generate_code_verifier() != generate_code_verifier()


def test_generate_state_is_unique_per_call() -> None:
    assert generate_state() != generate_state()


def test_build_authorize_url_contains_pkce_challenge_and_exact_redirect_uri() -> None:
    verifier = "a" * 43
    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )

    url = build_authorize_url(
        client_id="client123",
        redirect_uri="http://127.0.0.1:8000/auth/callback",
        state="state123",
        code_verifier=verifier,
    )

    assert url.startswith("https://accounts.spotify.com/authorize")
    assert "client_id=client123" in url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8000%2Fauth%2Fcallback" in url
    assert "state=state123" in url
    assert f"code_challenge={expected_challenge}" in url
    assert "code_challenge_method=S256" in url
    assert "playlist-read-private" in url
    assert "playlist-read-collaborative" in url


class FakeAuthHttpClient:
    def __init__(self, exchange_response=None, refresh_response=None) -> None:
        self.exchange_response = exchange_response
        self.refresh_response = refresh_response
        self.exchange_calls: list[dict] = []
        self.refresh_calls: list[dict] = []

    def exchange_code(self, code: str, redirect_uri: str, client_id: str, code_verifier: str) -> dict:
        self.exchange_calls.append(
            {"code": code, "redirect_uri": redirect_uri, "client_id": client_id, "code_verifier": code_verifier}
        )
        return self.exchange_response

    def refresh_token(self, refresh_token: str, client_id: str) -> dict:
        self.refresh_calls.append({"refresh_token": refresh_token, "client_id": client_id})
        return self.refresh_response


def test_exchange_code_returns_tokens_with_expiry() -> None:
    http = FakeAuthHttpClient(
        exchange_response={"access_token": "acc", "refresh_token": "ref", "expires_in": 3600}
    )
    client = SpotifyAuthClient(client_id="client123", http_client=http)

    tokens = client.exchange_code(code="code123", redirect_uri="http://127.0.0.1:8000/auth/callback", code_verifier="verifier")

    assert tokens.access_token == "acc"
    assert tokens.refresh_token == "ref"
    assert tokens.expires_at > 0
    assert http.exchange_calls[0]["client_id"] == "client123"


def test_refresh_reuses_old_refresh_token_when_not_rotated() -> None:
    http = FakeAuthHttpClient(refresh_response={"access_token": "new-acc", "expires_in": 3600})
    client = SpotifyAuthClient(client_id="client123", http_client=http)

    tokens = client.refresh("old-refresh")

    assert tokens.access_token == "new-acc"
    assert tokens.refresh_token == "old-refresh"


def test_refresh_uses_rotated_refresh_token_when_present() -> None:
    http = FakeAuthHttpClient(refresh_response={"access_token": "new-acc", "refresh_token": "new-refresh", "expires_in": 3600})
    client = SpotifyAuthClient(client_id="client123", http_client=http)

    tokens = client.refresh("old-refresh")

    assert tokens.refresh_token == "new-refresh"
