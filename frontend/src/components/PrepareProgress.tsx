import type { PrepareStatus } from "../types/api";

interface PrepareProgressProps {
  status: PrepareStatus;
}

export function PrepareProgress({ status }: PrepareProgressProps) {
  const percent = status.total > 0 ? Math.round((status.processed / status.total) * 100) : 0;

  if (status.state === "error") {
    return (
      <div className="error-banner">
        Failed to prepare this playlist{status.error ? `: ${status.error}` : "."}
      </div>
    );
  }

  return (
    <div className="prepare-progress">
      <div className="prepare-progress-track">
        <div className="prepare-progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <div className="prepare-progress-text">
        {status.state === "done" ? (
          <span>
            Ready: {status.with_lyrics} of {status.total} tracks have lyrics
            {status.instrumental > 0 && `, ${status.instrumental} instrumental`}
            {status.missing > 0 && `, ${status.missing} missing`}.
          </span>
        ) : (
          <span>
            Analyzing lyrics: {status.processed} of {status.total} tracks processed
            {status.with_lyrics > 0 && ` (${status.with_lyrics} with lyrics so far)`}.
          </span>
        )}
      </div>
    </div>
  );
}
