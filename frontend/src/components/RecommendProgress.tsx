import type { RecommendJobStatus } from "../types/api";

interface RecommendProgressProps {
  status: RecommendJobStatus;
}

export function RecommendProgress({ status }: RecommendProgressProps) {
  const percent = status.total > 0 ? Math.round((status.processed / status.total) * 100) : 0;

  if (status.state === "error") {
    return (
      <div className="error-banner">
        Failed to get a recommendation{status.error ? `: ${status.error}` : "."}
      </div>
    );
  }

  return (
    <div className="prepare-progress">
      <div className="prepare-progress-track">
        <div className="prepare-progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <div className="prepare-progress-text">
        {status.total > 0 ? (
          <span>
            {status.phase}: {status.processed} of {status.total} ({percent}%)
          </span>
        ) : (
          <span>{status.phase}...</span>
        )}
      </div>
    </div>
  );
}
