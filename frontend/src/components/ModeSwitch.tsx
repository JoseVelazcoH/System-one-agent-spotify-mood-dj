export type Mode = "library" | "discover";

interface ModeSwitchProps {
  mode: Mode;
  onChange: (mode: Mode) => void;
}

export function ModeSwitch({ mode, onChange }: ModeSwitchProps) {
  return (
    <div className="mode-switch">
      <button
        type="button"
        className={`mode-switch-option ${mode === "library" ? "is-active" : ""}`}
        onClick={() => onChange("library")}
      >
        My playlists
      </button>
      <button
        type="button"
        className={`mode-switch-option ${mode === "discover" ? "is-active" : ""}`}
        onClick={() => onChange("discover")}
      >
        Discover
      </button>
    </div>
  );
}
