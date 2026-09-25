import type { RecommendResponse } from "../types/api";

interface DecisionTraceProps {
  decision: RecommendResponse;
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function DecisionTrace({ decision }: DecisionTraceProps) {
  const sortedStrategies = Object.entries(decision.strategy_probabilities).sort(
    (a, b) => b[1] - a[1],
  );

  return (
    <section className="decision-trace">
      <h2 className="section-title">Decision trace</h2>

      <div className="strategy-block">
        <div className="strategy-chosen">
          Strategy: <strong>{decision.strategy}</strong>
        </div>
        <div className="strategy-bars">
          {sortedStrategies.map(([strategy, probability]) => (
            <div key={strategy} className="strategy-bar-row">
              <span className="strategy-bar-label">{strategy}</span>
              <div className="strategy-bar-track">
                <div
                  className={`strategy-bar-fill ${strategy === decision.strategy ? "is-chosen" : ""}`}
                  style={{ width: formatPercent(probability) }}
                />
              </div>
              <span className="strategy-bar-value">{formatPercent(probability)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="stages-block">
        {decision.stages.map((stage, index) => (
          <div key={stage.name} className="stage-card">
            <div className="stage-header">
              <span className="stage-index">Stage {index + 1}</span>
              <span className="stage-name">{stage.name}</span>
            </div>
            <div className="stage-targets">
              <TargetBar label="Energy" value={stage.profile.energy} />
              <TargetBar label="Valence" value={stage.profile.valence} />
              <TargetBar
                label="Tempo"
                value={stage.profile.tempo / 200}
                displayValue={`${Math.round(stage.profile.tempo)} BPM`}
              />
              <TargetBar label="Instrumental" value={stage.profile.instrumentalness} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

interface TargetBarProps {
  label: string;
  value: number;
  displayValue?: string;
}

function TargetBar({ label, value, displayValue }: TargetBarProps) {
  const clamped = Math.min(1, Math.max(0, value));
  return (
    <div className="target-bar-row">
      <span className="target-bar-label">{label}</span>
      <div className="target-bar-track">
        <div className="target-bar-fill" style={{ width: `${clamped * 100}%` }} />
      </div>
      <span className="target-bar-value">{displayValue ?? formatPercent(clamped)}</span>
    </div>
  );
}
