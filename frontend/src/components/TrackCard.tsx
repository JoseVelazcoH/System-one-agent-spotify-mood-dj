interface TrackCardData {
  id: string;
  name: string;
  artist: string;
  album: string;
  cover_url: string | null;
  external_url: string | null;
  keep_probability: number | null;
  tone?: number;
}

interface TrackCardProps {
  track: TrackCardData;
}

function toneLabel(tone: number): string {
  if (tone < 0.34) return "melancholic";
  if (tone < 0.67) return "hopeful";
  return "positive";
}

export function TrackCard({ track }: TrackCardProps) {
  return (
    <a
      className="track-card"
      href={track.external_url ?? undefined}
      target="_blank"
      rel="noreferrer"
    >
      <div className="track-cover">
        {track.cover_url ? (
          <img src={track.cover_url} alt={`${track.album} cover`} loading="lazy" />
        ) : (
          <div className="track-cover-placeholder">No cover</div>
        )}
      </div>
      <div className="track-info">
        <div className="track-name">{track.name}</div>
        <div className="track-artist">{track.artist}</div>
        <div className="track-meta-row">
          {track.keep_probability !== null && (
            <span className="track-probability">fit: {Math.round(track.keep_probability * 100)}%</span>
          )}
          {track.tone !== undefined && (
            <span className={`track-tone track-tone-${toneLabel(track.tone)}`}>{toneLabel(track.tone)}</span>
          )}
        </div>
      </div>
    </a>
  );
}
