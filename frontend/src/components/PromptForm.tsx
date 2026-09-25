import { useState, type FormEvent } from "react";

const DEFAULT_EXAMPLE_PROMPTS = [
  "I'm sad but want to feel better",
  "I need energy for the gym",
  "Match how I feel right now, nothing more",
  "Help me wind down before sleep",
  "Estoy triste pero quiero sentirme mejor",
  "Necesito energia para entrenar",
];

interface PromptFormProps {
  onSubmit: (prompt: string) => void;
  isLoading: boolean;
  examples?: string[];
}

export function PromptForm({ onSubmit, isLoading, examples }: PromptFormProps) {
  const [prompt, setPrompt] = useState("");
  const examplePrompts = examples ?? DEFAULT_EXAMPLE_PROMPTS;

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = prompt.trim();
    if (trimmed.length === 0) {
      return;
    }
    onSubmit(trimmed);
  };

  const handleExampleClick = (example: string) => {
    setPrompt(example);
    onSubmit(example);
  };

  return (
    <div className="prompt-panel">
      <form className="prompt-form" onSubmit={handleSubmit}>
        <input
          className="prompt-input"
          type="text"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Describe how you feel and what you want..."
          disabled={isLoading}
        />
        <button className="prompt-submit" type="submit" disabled={isLoading}>
          {isLoading ? "Deciding..." : "Get playlist"}
        </button>
      </form>
      <div className="example-prompts">
        {examplePrompts.map((example) => (
          <button
            key={example}
            type="button"
            className="example-chip"
            onClick={() => handleExampleClick(example)}
            disabled={isLoading}
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
