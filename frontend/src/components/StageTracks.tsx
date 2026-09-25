import { TrackCard } from "./TrackCard";

interface StageTracksProps {
  name: string;
  tracks: Array<{
    id: string;
    name: string;
    artist: string;
    album: string;
    cover_url: string | null;
    external_url: string | null;
    keep_probability: number | null;
    tone?: number;
  }>;
  index: number;
}

export function StageTracks({ name, tracks, index }: StageTracksProps) {
  return (
    <div className="stage-tracks-block">
      <div className="stage-tracks-title">
        Stage {index + 1}: {name}
      </div>
      {tracks.length === 0 ? (
        <div className="stage-tracks-empty">No tracks cleared the fit threshold for this stage.</div>
      ) : (
        <div className="track-grid">
          {tracks.map((track) => (
            <TrackCard key={track.id} track={track} />
          ))}
        </div>
      )}
    </div>
  );
}
