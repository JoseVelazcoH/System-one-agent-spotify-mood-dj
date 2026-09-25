import { useEffect, useRef, useState } from "react";
import "./App.css";
import {
  ApiError,
  fetchMe,
  fetchPlaylists,
  fetchPrepareStatus,
  fetchRecommendJob,
  loginUrl,
  logout,
  preparePlaylist,
  startRecommendJob,
} from "./api";
import { PlaylistPicker } from "./components/PlaylistPicker";
import { PlaylistResults } from "./components/PlaylistResults";
import { PrepareProgress } from "./components/PrepareProgress";
import { PromptForm } from "./components/PromptForm";
import { RecommendProgress } from "./components/RecommendProgress";
import type {
  PlaylistRecommendResponse,
  PlaylistSummary,
  PrepareStatus,
  RecommendJobStatus,
} from "./types/api";

const POLL_INTERVAL_MS = 1500;
const RECOMMEND_POLL_INTERVAL_MS = 1000;

function App() {
  const [authChecked, setAuthChecked] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [selectedPlaylist, setSelectedPlaylist] = useState<PlaylistSummary | null>(null);
  const [prepareStatus, setPrepareStatus] = useState<PrepareStatus | null>(null);
  const [playlistResult, setPlaylistResult] = useState<PlaylistRecommendResponse | null>(null);
  const [playlistLoading, setPlaylistLoading] = useState(false);
  const [recommendStatus, setRecommendStatus] = useState<RecommendJobStatus | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recommendPollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (authChecked) {
      return;
    }
    fetchMe()
      .then((me) => {
        setLoggedIn(me.logged_in);
        setAuthChecked(true);
      })
      .catch(() => {
        setLoggedIn(false);
        setAuthChecked(true);
      });
  }, [authChecked]);

  useEffect(() => {
    if (!authChecked || !loggedIn) {
      return;
    }
    setLibraryError(null);
    fetchPlaylists()
      .then(setPlaylists)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          setLoggedIn(false);
          return;
        }
        setLibraryError(err instanceof Error ? err.message : "Failed to load playlists");
      });
  }, [authChecked, loggedIn]);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
      if (recommendPollTimerRef.current) {
        clearInterval(recommendPollTimerRef.current);
      }
    };
  }, []);

  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const pollStatus = (playlistId: string) => {
    stopPolling();
    pollTimerRef.current = setInterval(async () => {
      try {
        const status = await fetchPrepareStatus(playlistId);
        setPrepareStatus(status);
        if (status.state === "done" || status.state === "error") {
          stopPolling();
        }
      } catch (err) {
        stopPolling();
        setLibraryError(err instanceof Error ? err.message : "Failed to check preparation status");
      }
    }, POLL_INTERVAL_MS);
  };

  const handleSelectPlaylist = async (playlist: PlaylistSummary) => {
    stopPolling();
    stopRecommendPolling();
    setSelectedPlaylist(playlist);
    window.scrollTo({ top: 0, behavior: "smooth" });
    setPlaylistResult(null);
    setRecommendStatus(null);
    setPlaylistLoading(false);
    setLibraryError(null);
    setPrepareStatus({ state: "running", total: 0, processed: 0, with_lyrics: 0, instrumental: 0, missing: 0, error: null });
    try {
      await preparePlaylist(playlist.id);
      const status = await fetchPrepareStatus(playlist.id);
      setPrepareStatus(status);
      if (status.state !== "done" && status.state !== "error") {
        pollStatus(playlist.id);
      }
    } catch (err) {
      setLibraryError(err instanceof Error ? err.message : "Failed to prepare playlist");
    }
  };

  const stopRecommendPolling = () => {
    if (recommendPollTimerRef.current) {
      clearInterval(recommendPollTimerRef.current);
      recommendPollTimerRef.current = null;
    }
  };

  const pollRecommendJob = (jobId: string) => {
    stopRecommendPolling();
    recommendPollTimerRef.current = setInterval(async () => {
      try {
        const status = await fetchRecommendJob(jobId);
        setRecommendStatus(status);
        if (status.state === "done") {
          stopRecommendPolling();
          setPlaylistResult(status.result);
          setPlaylistLoading(false);
        } else if (status.state === "error") {
          stopRecommendPolling();
          setLibraryError(status.error ?? "Failed to get recommendation");
          setPlaylistLoading(false);
        }
      } catch (err) {
        stopRecommendPolling();
        setPlaylistLoading(false);
        setLibraryError(err instanceof Error ? err.message : "Failed to check recommendation status");
      }
    }, RECOMMEND_POLL_INTERVAL_MS);
  };

  const handlePlaylistSubmit = async (prompt: string) => {
    if (!selectedPlaylist) {
      return;
    }
    setPlaylistLoading(true);
    setLibraryError(null);
    setPlaylistResult(null);
    setRecommendStatus({ state: "running", phase: "detecting mood", processed: 0, total: 0, result: null, error: null });
    try {
      const { job_id: jobId } = await startRecommendJob(selectedPlaylist.id, prompt);
      pollRecommendJob(jobId);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setLoggedIn(false);
        setLibraryError("Your Spotify session expired. Please connect again.");
      } else if (err instanceof ApiError && err.status === 409) {
        setLibraryError("This playlist isn't prepared yet. Please wait for preparation to finish.");
      } else {
        setLibraryError(err instanceof Error ? err.message : "Failed to get recommendation");
      }
      setPlaylistResult(null);
      setRecommendStatus(null);
      setPlaylistLoading(false);
    }
  };

  const handleLogout = async () => {
    stopPolling();
    stopRecommendPolling();
    await logout().catch(() => undefined);
    setLoggedIn(false);
    setPlaylists([]);
    setSelectedPlaylist(null);
    setPrepareStatus(null);
    setPlaylistResult(null);
    setRecommendStatus(null);
    setPlaylistLoading(false);
  };

  const promptDisabledReason = (): string | null => {
    if (!selectedPlaylist) {
      return "Pick one of your playlists below to start.";
    }
    if (prepareStatus?.state === "error") {
      return "Preparing this playlist failed. Pick it again to retry.";
    }
    if (prepareStatus?.state !== "done") {
      return `Reading lyrics for "${selectedPlaylist.name}"... the prompt unlocks when it finishes.`;
    }
    return null;
  };

  const renderLibrary = () => {
    if (!authChecked) {
      return <div className="stage-tracks-empty">Checking Spotify session...</div>;
    }

    if (!loggedIn) {
      return (
        <div className="connect-panel">
          <p>Connect your Spotify account to analyze your own playlists.</p>
          <a className="prompt-submit connect-button" href={loginUrl()}>
            Connect Spotify
          </a>
        </div>
      );
    }

    return (
      <div className="library-panel">
        <div className="library-header">
          <span className="library-header-text">Logged in with Spotify</span>
          <button type="button" className="example-chip" onClick={handleLogout}>
            Log out
          </button>
        </div>

        {selectedPlaylist && prepareStatus && (
          <div className="prepare-panel">
            <div className="prepare-panel-title">Preparing "{selectedPlaylist.name}"</div>
            <PrepareProgress status={prepareStatus} />
          </div>
        )}

        <PromptForm
          onSubmit={handlePlaylistSubmit}
          isLoading={playlistLoading}
          disabledReason={promptDisabledReason()}
        />

        {playlistLoading && recommendStatus && (
          <div className="prepare-panel">
            <div className="prepare-panel-title">Building your playlist</div>
            <RecommendProgress status={recommendStatus} />
          </div>
        )}

        {libraryError && <div className="error-banner">{libraryError}</div>}

        {playlistResult && <PlaylistResults result={playlistResult} />}

        <PlaylistPicker
          playlists={playlists}
          selectedId={selectedPlaylist?.id ?? null}
          onSelect={handleSelectPlaylist}
        />
      </div>
    );
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1 className="app-title">Laya Mood DJ</h1>
        <p className="app-subtitle">
          A decision model picks the strategy, target sound and tracks. No LLM ranking.
        </p>
      </header>

      {renderLibrary()}
    </div>
  );
}

export default App;
