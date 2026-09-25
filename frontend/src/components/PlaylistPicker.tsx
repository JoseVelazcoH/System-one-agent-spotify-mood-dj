import type { PlaylistSummary } from "../types/api";

interface PlaylistPickerProps {
  playlists: PlaylistSummary[];
  selectedId: string | null;
  onSelect: (playlist: PlaylistSummary) => void;
}

export function PlaylistPicker({ playlists, selectedId, onSelect }: PlaylistPickerProps) {
  if (playlists.length === 0) {
    return <div className="stage-tracks-empty">No playlists found on your Spotify account.</div>;
  }

  return (
    <div className="playlist-grid">
      {playlists.map((playlist) => (
        <button
          type="button"
          key={playlist.id}
          className={`playlist-card ${playlist.id === selectedId ? "is-selected" : ""}`}
          onClick={() => onSelect(playlist)}
        >
          <div className="playlist-cover">
            {playlist.image_url ? (
              <img src={playlist.image_url} alt={`${playlist.name} cover`} loading="lazy" />
            ) : (
              <div className="track-cover-placeholder">No cover</div>
            )}
          </div>
          <div className="playlist-name">{playlist.name}</div>
          <div className="playlist-track-count">{playlist.track_count} tracks</div>
        </button>
      ))}
    </div>
  );
}
