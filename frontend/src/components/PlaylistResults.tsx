import type { PlaylistRecommendResponse } from "../types/api";
import { SignalBars } from "./SignalBars";
import { StageTracks } from "./StageTracks";

interface PlaylistResultsProps {
  result: PlaylistRecommendResponse;
}

export function PlaylistResults({ result }: PlaylistResultsProps) {
  return (
    <main className="results">
      <section className="decision-trace">
        <h2 className="section-title">Decision trace</h2>
        <SignalBars strategy={result.strategy} signals={result.signals} />
        {(result.excluded.no_lyrics > 0 || result.excluded.instrumental > 0) && (
          <div className="excluded-note">
            Excluded {result.excluded.no_lyrics} tracks without lyrics and{" "}
            {result.excluded.instrumental} instrumental tracks from the mood analysis.
          </div>
        )}
      </section>
      <section className="playlist">
        <h2 className="section-title">Playlist</h2>
        {result.stages.map((stage, index) => (
          <StageTracks key={stage.name} name={stage.name} tracks={stage.tracks} index={index} />
        ))}
      </section>
    </main>
  );
}
