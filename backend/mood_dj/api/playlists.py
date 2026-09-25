"""Playlist listing and preparation endpoints, requiring a logged-in session."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from mood_dj.api.deps import (
    get_current_tokens,
    get_job_manager,
    get_playlists_client,
    get_recommend_from_playlist_use_case,
)
from mood_dj.api.schemas import (
    ExcludedResponse,
    PlaylistRecommendResponse,
    PlaylistStageResponse,
    PlaylistSummaryResponse,
    PlaylistTrackResponse,
    PrepareStatusResponse,
    RecommendFromPlaylistRequest,
)
from mood_dj.application.prepare_job_manager import PrepareJobManager
from mood_dj.application.recommend_from_playlist import (
    PlaylistNotPreparedError,
    RecommendFromPlaylistUseCase,
)
from mood_dj.domain.models import PrepareState, SpotifyTokens
from mood_dj.ports.spotify_playlists import SpotifyPlaylistsClient

router = APIRouter(prefix="/playlists", tags=["playlists"])

NOT_PREPARED_DETAIL = "Playlist not prepared yet. Call POST /playlists/{id}/prepare first."


@router.get("", response_model=list[PlaylistSummaryResponse])
def list_playlists(
    tokens: SpotifyTokens = Depends(get_current_tokens),
    playlists_client: SpotifyPlaylistsClient = Depends(get_playlists_client),
):
    playlists = playlists_client.list_playlists(tokens.access_token)
    return [
        PlaylistSummaryResponse(
            id=p.id, name=p.name, image_url=p.image_url, track_count=p.track_count, snapshot_id=p.snapshot_id
        )
        for p in playlists
    ]


@router.post("/{playlist_id}/prepare")
def prepare_playlist(
    playlist_id: str,
    tokens: SpotifyTokens = Depends(get_current_tokens),
    job_manager: PrepareJobManager = Depends(get_job_manager),
):
    started = job_manager.start(playlist_id, tokens.access_token)
    return {"started": started}


@router.get("/{playlist_id}/status", response_model=PrepareStatusResponse)
def prepare_status(
    playlist_id: str,
    tokens: SpotifyTokens = Depends(get_current_tokens),
    job_manager: PrepareJobManager = Depends(get_job_manager),
):
    progress = job_manager.status(playlist_id)
    return PrepareStatusResponse(
        state=progress.state.value,
        total=progress.total,
        processed=progress.processed,
        with_lyrics=progress.with_lyrics,
        instrumental=progress.instrumental,
        missing=progress.missing,
        error=progress.error,
    )


@router.post("/{playlist_id}/recommend", response_model=PlaylistRecommendResponse)
def recommend_from_playlist(
    playlist_id: str,
    request: RecommendFromPlaylistRequest,
    tokens: SpotifyTokens = Depends(get_current_tokens),
    job_manager: PrepareJobManager = Depends(get_job_manager),
    use_case: RecommendFromPlaylistUseCase = Depends(get_recommend_from_playlist_use_case),
):
    if job_manager.status(playlist_id).state != PrepareState.DONE:
        raise HTTPException(status_code=409, detail=NOT_PREPARED_DETAIL)

    try:
        recommendation = use_case.run(request.prompt, playlist_id, tokens.access_token)
    except PlaylistNotPreparedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return PlaylistRecommendResponse(
        strategy=recommendation.strategy.value,
        signals=recommendation.signal_probabilities,
        stages=[
            PlaylistStageResponse(
                name=stage.name,
                tracks=[
                    PlaylistTrackResponse(
                        id=ranked.track.id,
                        name=ranked.track.name,
                        artist=ranked.track.artist,
                        album=ranked.track.album,
                        cover_url=ranked.track.cover_url,
                        external_url=ranked.track.external_url,
                        keep_probability=ranked.fit,
                        tone=ranked.tone,
                    )
                    for ranked in stage.tracks
                ],
            )
            for stage in recommendation.stages
        ],
        excluded=ExcludedResponse(
            no_lyrics=recommendation.excluded_no_lyrics,
            instrumental=recommendation.excluded_instrumental,
        ),
    )
