"""DecisionEngine adapter backed by the real Laya Router.

Laya's `Router().predict(state, questions)` answers typed questions in one forward
pass and returns `{"answers": {qid: {...}}}`. Question types confirmed by reading
the installed `laya` package source (`laya/agent.py`, `laya/common.py`):

- "choice": `{"type": "choice", "instructions": str, "criteria": {label: description}}`.
  Answer: `{"choice": <label>, "probabilities": {label: float, ...}, ...}`.
- "score": `{"type": "score", "instructions": str, "criteria": [level0_desc, level1_desc, ...]}`.
  Answer: `{"score": <expected index, float>, "probabilities": {"0": float, ...}, ...}`.
- "noul" (a yes/no question; there is no literal "yes_no" type in the package):
  `{"type": "noul", "instructions": str, "criteria": {"false": desc, "true": desc}}`.
  Answer: `{"noul": <probability the statement is true>, ...}`.

This adapter is exercised end to end by `tests/integration/test_laya_decision_engine.py`,
marked `laya` and skipped by default because it downloads real model weights.
"""

from __future__ import annotations

from mood_dj.domain.models import MoodProfile, Strategy, Track

STRATEGY_CRITERIA = {
    Strategy.ACCOMPANY.value: (
        "The listener feels a certain way and wants company in that feeling, not a change of "
        "mood: for example, feeling sad and wanting something to keep them company."
    ),
    Strategy.LIFT.value: (
        "The listener feels down, sad or low but wants to feel better, cheer up or get out of "
        "that mood."
    ),
    Strategy.ENERGIZE.value: (
        "The listener is happy or energetic and wants to move: dance, work out or power through "
        "an activity."
    ),
    Strategy.CALM.value: (
        "The listener wants to relax, wind down or sleep, and needs the energy and tempo brought "
        "down."
    ),
}

# Score levels are index 0..4; the adapter maps the returned expected index to a 0.0-1.0 value.
NORMALIZED_LEVELS = [
    "very low",
    "low",
    "medium",
    "high",
    "very high",
]

TEMPO_LEVELS_BPM = [70.0, 95.0, 115.0, 135.0, 160.0]

TARGET_QUESTIONS = {
    "energy": {
        "type": "score",
        "instructions": "How much energy should the music have for this moment?",
        "criteria": NORMALIZED_LEVELS,
    },
    "valence": {
        "type": "score",
        "instructions": "How positive or upbeat should the music feel for this moment?",
        "criteria": NORMALIZED_LEVELS,
    },
    "tempo": {
        "type": "score",
        "instructions": "How fast should the tempo be for this moment?",
        "criteria": NORMALIZED_LEVELS,
    },
    "instrumentalness": {
        "type": "score",
        "instructions": "How much should the track lean instrumental over vocal-heavy?",
        "criteria": NORMALIZED_LEVELS,
    },
}

KEEP_QUESTION_ID = "keep"

# How many keep-decision requests to run through the model in a single forward pass.
KEEP_BATCH_SIZE = 12


def _level(value: float, low_max: float, medium_max: float) -> str:
    if value < low_max:
        return "low"
    if value < medium_max:
        return "medium"
    return "high"


def _mood_word(valence: float) -> str:
    if valence < 0.35:
        return "sad/melancholic"
    if valence < 0.65:
        return "neutral"
    return "happy"


def _tempo_word(tempo: float) -> str:
    if tempo < 100:
        return "slow"
    if tempo < 130:
        return "moderate"
    return "fast"


def describe_track_in_words(track: Track) -> str:
    """Describe a track's audio features in plain words instead of raw floats.

    Laya answers questions in natural language, so handing it bare feature floats
    (e.g. `energy=0.15`) gives it little to reason with. A short verbal description
    (e.g. "energy: low, mood: sad/melancholic, tempo: slow ~70 BPM, mostly vocal,
    acoustic") is far more informative for the "does this fit the moment" question.
    """
    energy = _level(track.energy, 0.4, 0.7)
    mood = _mood_word(track.valence)
    tempo_word = _tempo_word(track.tempo)
    vocal = "mostly instrumental" if track.instrumentalness >= 0.5 else "mostly vocal"
    texture = "acoustic" if track.acousticness >= 0.5 else "electronic"

    return (
        f"energy: {energy}, mood: {mood}, tempo: {tempo_word} ~{track.tempo:.0f} BPM, "
        f"{vocal}, {texture}"
    )


class LayaDecisionEngine:
    """Adapts the Laya Router to the DecisionEngine port."""

    def __init__(self, router=None) -> None:
        if router is None:
            from laya import Router

            router = Router()
        self._router = router

    def decide_strategy(self, prompt: str) -> tuple[Strategy, dict[str, float]]:
        questions = {
            "strategy": {
                "type": "choice",
                "instructions": "Which strategy best fits what the listener is asking for?",
                "criteria": STRATEGY_CRITERIA,
            }
        }
        result = self._router.predict(prompt, questions)
        answer = result["answers"]["strategy"]
        return Strategy(answer["choice"]), dict(answer["probabilities"])

    def decide_targets(self, prompt: str, strategy: Strategy, stage_name: str) -> MoodProfile:
        state = {"prompt": prompt, "strategy": strategy.value, "stage": stage_name}
        result = self._router.predict(state, TARGET_QUESTIONS)
        answers = result["answers"]
        max_index = len(NORMALIZED_LEVELS) - 1

        def normalized(question_id: str) -> float:
            return max(0.0, min(1.0, answers[question_id]["score"] / max_index))

        tempo_score = normalized("tempo")
        tempo_bpm = TEMPO_LEVELS_BPM[0] + tempo_score * (TEMPO_LEVELS_BPM[-1] - TEMPO_LEVELS_BPM[0])

        return MoodProfile(
            energy=normalized("energy"),
            valence=normalized("valence"),
            tempo=tempo_bpm,
            instrumentalness=normalized("instrumentalness"),
        )

    def decide_keep(self, prompt: str, track: Track) -> float:
        result = self._router.predict(self._keep_state(prompt, track), self._keep_questions())
        return float(result["answers"][KEEP_QUESTION_ID]["noul"])

    def decide_keep_many(self, prompt: str, tracks: list[Track]) -> list[float]:
        if not tracks:
            return []
        questions = self._keep_questions()
        requests = [
            {"state": self._keep_state(prompt, track), "questions": questions} for track in tracks
        ]
        results = self._router.predict_batch(requests, batch_size=KEEP_BATCH_SIZE)
        return [float(result["answers"][KEEP_QUESTION_ID]["noul"]) for result in results]

    def _keep_state(self, prompt: str, track: Track) -> dict:
        return {
            "prompt": prompt,
            "track": {
                "name": track.name,
                "artist": track.artist,
                "description": describe_track_in_words(track),
            },
        }

    def _keep_questions(self) -> dict:
        return {
            KEEP_QUESTION_ID: {
                "type": "noul",
                "instructions": "Does this track fit the listener's current moment?",
                "criteria": {
                    "false": "The track does not fit this moment.",
                    "true": "The track fits this moment well.",
                },
            }
        }
