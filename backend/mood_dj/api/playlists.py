"""Playlist listing and preparation endpoints, requiring a logged-in session."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from mood_dj.api.deps import (
    get_current_tokens,
    get_job_manager,
    get_playlists_client,
    get_recommend_job_manager,
    get_session_id,
)
from mood_dj.api.schemas import (
    ExcludedResponse,
    PlaylistRecommendResponse,
    PlaylistStageResponse,
    PlaylistSummaryResponse,
    PlaylistTrackResponse,
    PrepareStatusResponse,
    RecommendFromPlaylistRequest,
    RecommendJobStartedResponse,
    RecommendJobStatusResponse,
)
from mood_dj.application.prepare_job_manager import PrepareJobManager
from mood_dj.application.recommend_from_playlist import PlaylistRecommendation
from mood_dj.application.recommend_job_manager import RecommendJobManager
from mood_dj.domain.models import PrepareState, SpotifyTokens
from mood_dj.ports.spotify_playlists import SpotifyPlaylistsClient

router = APIRouter(prefix="/playlists", tags=["playlists"])
recommend_jobs_router = APIRouter(prefix="/recommend-jobs", tags=["playlists"])

NOT_PREPARED_DETAIL = "Playlist not prepared yet. Call POST /playlists/{id}/prepare first."


def _to_response(recommendation: PlaylistRecommendation) -> PlaylistRecommendResponse:
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


@router.post("/{playlist_id}/recommend", response_model=RecommendJobStartedResponse, status_code=202)
def recommend_from_playlist(
    playlist_id: str,
    request: RecommendFromPlaylistRequest,
    tokens: SpotifyTokens = Depends(get_current_tokens),
    session_id: str = Depends(get_session_id),
    job_manager: PrepareJobManager = Depends(get_job_manager),
    recommend_job_manager: RecommendJobManager = Depends(get_recommend_job_manager),
):
    if job_manager.status(playlist_id).state != PrepareState.DONE:
        raise HTTPException(status_code=409, detail=NOT_PREPARED_DETAIL)

    job_id = recommend_job_manager.start(session_id, playlist_id, request.prompt, tokens.access_token)
    return RecommendJobStartedResponse(job_id=job_id)


@recommend_jobs_router.get("/{job_id}", response_model=RecommendJobStatusResponse)
def recommend_job_status(
    job_id: str,
    tokens: SpotifyTokens = Depends(get_current_tokens),
    session_id: str = Depends(get_session_id),
    recommend_job_manager: RecommendJobManager = Depends(get_recommend_job_manager),
):
    job = recommend_job_manager.status(job_id, session_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Recommend job not found.")

    return RecommendJobStatusResponse(
        state=job.state.value,
        phase=job.phase,
        processed=job.processed,
        total=job.total,
        result=_to_response(job.result) if job.result is not None else None,
        error=job.error,
    )
