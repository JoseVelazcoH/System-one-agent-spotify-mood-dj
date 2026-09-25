const SIGNAL_LABELS: Record<string, string> = {
  feels_bad: "Feels down",
  wants_change: "Wants a change",
  wants_energy: "Wants energy",
  wants_rest: "Wants rest",
};

const SIGNAL_ORDER = ["feels_bad", "wants_change", "wants_energy", "wants_rest"];

interface SignalBarsProps {
  strategy: string;
  signals: Record<string, number>;
}

export function SignalBars({ strategy, signals }: SignalBarsProps) {
  const ordered = SIGNAL_ORDER.filter((key) => key in signals);

  return (
    <div className="strategy-block">
      <div className="strategy-chosen">
        Strategy: <strong>{strategy}</strong>
      </div>
      <div className="strategy-bars">
        {ordered.map((key) => {
          const value = signals[key];
          const percent = Math.round(value * 100);
          return (
            <div key={key} className="strategy-bar-row">
              <span className="strategy-bar-label">{SIGNAL_LABELS[key] ?? key}</span>
              <div className="strategy-bar-track">
                <div className="strategy-bar-fill" style={{ width: `${percent}%` }} />
              </div>
              <span className="strategy-bar-value">{percent}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
