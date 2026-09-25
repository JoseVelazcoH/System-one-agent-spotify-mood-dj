import { useEffect, useRef, useState } from "react";
import "./App.css";
import {
  ApiError,
  fetchMe,
  fetchPlaylistRecommendation,
  fetchPlaylists,
  fetchPrepareStatus,
  fetchRecommendation,
  loginUrl,
  logout,
  preparePlaylist,
} from "./api";
import { DecisionTrace } from "./components/DecisionTrace";
import { ModeSwitch, type Mode } from "./components/ModeSwitch";
import { PlaylistPicker } from "./components/PlaylistPicker";
import { PlaylistResults } from "./components/PlaylistResults";
import { PrepareProgress } from "./components/PrepareProgress";
import { PromptForm } from "./components/PromptForm";
import { StageTracks } from "./components/StageTracks";
import type {
  PlaylistRecommendResponse,
  PlaylistSummary,
  PrepareStatus,
  RecommendResponse,
} from "./types/api";

const POLL_INTERVAL_MS = 1500;

function App() {
  const [mode, setMode] = useState<Mode>("library");

  // Discover mode state
  const [decision, setDecision] = useState<RecommendResponse | null>(null);
  const [discoverLoading, setDiscoverLoading] = useState(false);
  const [discoverError, setDiscoverError] = useState<string | null>(null);

  // Library mode state
  const [authChecked, setAuthChecked] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [selectedPlaylist, setSelectedPlaylist] = useState<PlaylistSummary | null>(null);
  const [prepareStatus, setPrepareStatus] = useState<PrepareStatus | null>(null);
  const [playlistResult, setPlaylistResult] = useState<PlaylistRecommendResponse | null>(null);
  const [playlistLoading, setPlaylistLoading] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (mode !== "library" || authChecked) {
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
  }, [mode, authChecked]);

  useEffect(() => {
    if (mode !== "library" || !authChecked || !loggedIn) {
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
  }, [mode, authChecked, loggedIn]);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
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
    setSelectedPlaylist(playlist);
    setPlaylistResult(null);
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

  const handleDiscoverSubmit = async (prompt: string) => {
    setDiscoverLoading(true);
    setDiscoverError(null);
    try {
      const result = await fetchRecommendation(prompt);
      setDecision(result);
    } catch (err) {
      setDiscoverError(err instanceof Error ? err.message : "Something went wrong");
      setDecision(null);
    } finally {
      setDiscoverLoading(false);
    }
  };

  const handlePlaylistSubmit = async (prompt: string) => {
    if (!selectedPlaylist) {
      return;
    }
    setPlaylistLoading(true);
    setLibraryError(null);
    try {
      const result = await fetchPlaylistRecommendation(selectedPlaylist.id, prompt);
      setPlaylistResult(result);
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
    } finally {
      setPlaylistLoading(false);
    }
  };

  const handleLogout = async () => {
    stopPolling();
    await logout().catch(() => undefined);
    setLoggedIn(false);
    setPlaylists([]);
    setSelectedPlaylist(null);
    setPrepareStatus(null);
    setPlaylistResult(null);
  };

  const renderLibraryMode = () => {
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

        {libraryError && <div className="error-banner">{libraryError}</div>}

        <PlaylistPicker
          playlists={playlists}
          selectedId={selectedPlaylist?.id ?? null}
          onSelect={handleSelectPlaylist}
        />

        {selectedPlaylist && prepareStatus && (
          <div className="prepare-panel">
            <div className="prepare-panel-title">Preparing "{selectedPlaylist.name}"</div>
            <PrepareProgress status={prepareStatus} />
          </div>
        )}

        {selectedPlaylist && prepareStatus?.state === "done" && (
          <PromptForm onSubmit={handlePlaylistSubmit} isLoading={playlistLoading} />
        )}

        {playlistResult && <PlaylistResults result={playlistResult} />}
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

      <ModeSwitch mode={mode} onChange={setMode} />

      {mode === "discover" ? (
        <>
          <PromptForm onSubmit={handleDiscoverSubmit} isLoading={discoverLoading} />

          {discoverError && <div className="error-banner">{discoverError}</div>}

          {decision && (
            <main className="results">
              <DecisionTrace decision={decision} />
              <section className="playlist">
                <h2 className="section-title">Playlist</h2>
                {decision.stages.map((stage, index) => (
                  <StageTracks key={stage.name} name={stage.name} tracks={stage.tracks} index={index} />
                ))}
              </section>
            </main>
          )}
        </>
      ) : (
        renderLibraryMode()
      )}
    </div>
  );
}

export default App;
