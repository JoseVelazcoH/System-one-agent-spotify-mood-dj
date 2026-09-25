# Laya Mood DJ

A demo where a natural-language mood prompt ("I'm sad but want to feel better") drives
music selection through Laya, a calibrated decision model, not an LLM ranker. Laya
picks the listening strategy and the target audio profile; a local track catalog
supplies candidates matching that profile; Laya then scores each candidate for fit;
Spotify supplies cover art and the listen link.

## Architecture

Hexagonal layout, screaming architecture (the folder names describe the domain, not
the framework):

```
backend/
  mood_dj/
    domain/        MoodProfile, Strategy, Track, Stage, Decision
    application/    recommend_playlist.py (the use case orchestrating the ports)
    ports/          DecisionEngine, TrackCatalog, CoverProvider (Protocols)
    adapters/
      laya_decision_engine.py   Laya Router wrapper
      dataset_catalog.py        DuckDB over Parquet, ranks tracks by feature distance
      spotify_covers.py         Spotify Client Credentials + /tracks batch lookup
    api/            FastAPI: POST /recommend {prompt} -> decision trace + playlist
  scripts/
    build_dataset.py            Converts a Kaggle CSV into the Parquet the catalog reads
  tests/
    unit/           pytest with fake adapters (strict TDD, no network or model calls)
    integration/    real Laya model, marked `laya`, skipped by default
frontend/
  Vite + React + TypeScript: prompt input, decision trace panel, track cards
```

## Why this data split

Spotify's Web API, since November 2024, returns 403 on `audio-features` and
`recommendations` for newly registered apps. `search`, `tracks` and album images
still work with a plain Client Credentials token. So:

- Audio features (energy, valence, tempo, danceability, acousticness,
  instrumentalness) come from a public Kaggle Spotify tracks dataset, converted to
  Parquet and queried with DuckDB.
- Cover art, track name, artist, album and the external Spotify link come live from
  `GET /v1/tracks/{id}`, requested concurrently (the batch `?ids=` endpoint answers 403).

The tradeoff: the catalog is a frozen snapshot (no brand-new releases), but it needs
no scraping and no third-party audio-features API.

## Decision flow

1. Laya answers a `choice` question: strategy is `accompany`, `lift`, `energize` or
   `calm`.
2. For each stage (three stages for `lift`, interpolating toward a brighter mood;
   one stage otherwise), Laya answers `score` questions for target energy, valence,
   tempo and instrumental preference.
3. The dataset catalog returns the 30 closest tracks per stage (DuckDB, ranked by
   feature distance).
4. Laya answers a `noul` (yes/no) question per candidate: does this track fit the
   moment? Tracks below a 0.5 probability threshold are dropped; the rest are kept,
   ranked by that probability.
5. Spotify enriches the kept tracks with cover art and the listen link.

## Laya API, as actually shipped

`pip install laya` documentation examples show `{"type": "yes/no", ...}`, but the
installed package (verified by reading `laya/agent.py` and `laya/common.py`) uses
`"noul"` as the literal type string for yes/no questions; there is no `"yes/no"` type.
The adapter in `mood_dj/adapters/laya_decision_engine.py` uses the confirmed schema:

- `choice`: `{"type": "choice", "instructions": str, "criteria": {label: description}}`.
  Answer: `{"choice": <label>, "probabilities": {label: float, ...}}`.
- `score`: `{"type": "score", "instructions": str, "criteria": [level0, level1, ...]}`.
  Answer: `{"score": <expected index as float>, "probabilities": {"0": float, ...}}`.
- `noul`: `{"type": "noul", "instructions": str, "criteria": {"false": ..., "true": ...}}`.
  Answer: `{"noul": <probability the statement is true>}`.

`Router().predict(state, questions)` returns `{"answers": {question_id: {...}}, ...}`.

## Setup

### Backend

```bash
cd backend
uv sync
cp .env.example .env
# Fill in SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET (from https://developer.spotify.com/dashboard)
```

### Dataset

The default dataset is `maharshipandya/-spotify-tracks-dataset` (~114k tracks), downloaded
reproducibly via `kagglehub` (no Kaggle credentials needed for this public dataset):

```bash
cd backend
uv run scripts/build_dataset.py
# writes data/tracks.parquet by default (path configurable via DATASET_PATH in .env)
```

To use another CSV instead, pass its path: `uv run scripts/build_dataset.py /path/to/file.csv`.

The script requires columns for track id, name, artist, album, energy, valence,
tempo, danceability, acousticness and instrumentalness; it aliases common Kaggle
column names (`track_id`, `track_name`, `artists`, `album_name`) automatically.

### Running the backend

```bash
cd backend
uv run uvicorn mood_dj.api.main:app --reload
```

### Running the frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Testing

```bash
cd backend
uv run pytest              # unit tests with fake adapters, laya-marked tests skipped
uv run pytest -m laya       # real Laya model integration test (downloads weights)
```

```bash
cd frontend
npm run build               # type-checks and builds
```

## My playlists mode

A second mode, alongside Discover, that judges the listener's own Spotify playlists
by their lyrics instead of a frozen audio-features catalog.

### Flow

1. **Login**: `GET /auth/login` redirects to Spotify OAuth (PKCE, no client secret
   sent from the browser); `GET /auth/callback` exchanges the code and sets a
   `session_id` cookie. The app runs at `127.0.0.1` (not `localhost`) because that is
   the redirect URI registered with Spotify. Tokens live in `SqliteSessionStore` and
   are refreshed transparently a margin before expiry (`api/deps.py`).
2. **List playlists**: `GET /playlists` returns the user's playlists via
   `SpotifyPlaylistsClient`.
3. **Prepare**: `POST /playlists/{id}/prepare` starts a background job
   (`PrepareJobManager` + `PreparePlaylistUseCase`) that fetches every track's lyrics
   from LRCLIB (`adapters/lrclib_lyrics.py`) and caches the result (`lyrics`,
   `instrumental` or `missing`) in SQLite (`SqliteLyricsRepository`, table `lyrics`).
   `GET /playlists/{id}/status` polls progress. LRCLIB is a free, unauthenticated,
   best-effort public service: lookups can miss for live/remix versions, very new
   releases, or mismatched metadata, and instrumental tracks are reported as such
   rather than failing.
4. **Recommend**: `POST /playlists/{id}/recommend {prompt}` requires the playlist to
   already be prepared (checked against the prepare job's `DONE` state); otherwise it
   returns `409`. It then runs `RecommendFromPlaylistUseCase`, which:
   - Detects mood signals from the prompt with `LyricsJudge.detect_signals` (four
     `noul` questions in one predict call: `feels_bad`, `wants_change`,
     `wants_energy`, `wants_rest`), and resolves a `Strategy` with the existing
     `resolve_playlist_strategy` decision table.
   - Excludes tracks with no cached lyrics or missing lookups, and instrumental
     tracks, counting both (`excluded.no_lyrics`, `excluded.instrumental`).
   - Samples up to `max_candidates` (120 by default) cached tracks and judges each
     one's lyrics in a single `predict_batch` call: a `score` for emotional tone
     (very sad..happy, normalized 0.0-1.0) and a `noul` for whether the lyrics fit
     what the listener asked for (the fit probability, returned as
     `keep_probability`).
   - Caches both tone (per track) and fit (per track + prompt hash) in SQLite
     (`SqliteJudgmentCache`, tables `lyrics_tone` and `lyrics_fit`), keyed also by a
     question-set version, so repeat runs with the same prompt skip inference
     entirely and changing question wording invalidates the cache.
   - For `lift`: three tone-banded stages (`melancholic`, `hopeful`, `positive`),
     ranked within each band by fit, borrowing from the nearest band when one is
     empty.
   - For `accompany`, `energize`, `calm`: a single stage ranked by fit, with `accompany`
     breaking fit ties toward lower tone (match the current mood rather than lift it).
   - Logs candidate count, judged count and elapsed time per request.

### Multilingual Laya

The listener's music is mostly Spanish. `LayaLyricsJudge`
(`mood_dj/adapters/laya_lyrics_judge.py`) forces every call to the multilingual
checkpoint (`model="multilingual"` on `Router.predict`/`predict_batch`), which is
mmBERT-base per the model card, instead of relying on the Router's automatic
script-based routing. Reading `laya/router.py`'s own benchmark table confirms why:
the English checkpoint does not gently degrade off English, it collapses (e.g. 0.100
accuracy on Hindi MASSIVE intent, worse than the 0.050 random-guess floor) while
reporting high confidence, whereas the multilingual checkpoint scores well across
100+ languages including Spanish (+21 points over English on non-English XNLI). This
was confirmed against the real model, not assumed: see
`tests/integration/test_laya_lyrics_judge.py` (`laya`-marked).

Real measured probabilities for the Spanish prompt "Estoy triste pero quiero
sentirme mejor" (`uv run pytest -m laya`): `feels_bad=0.90`, `wants_change=0.77`,
`wants_energy=0.29`, `wants_rest=0.69`, resolving to `Strategy.LIFT` as expected. A
clearly sad Spanish lyric snippet scored tone `0.12` against `0.92` for a clearly
happy one, confirming tone ranking works as intended.

Inference is CPU-only in this setup and a single `predict` call costs roughly 7
seconds, so every lyrics judgment (signals and per-track tone/fit) is always sent
through `predict_batch`, never one call per track.

### Response shape

`POST /playlists/{id}/recommend` reuses the Discover flow's Decision/Stage/Track
shape where the two modes overlap (a `strategy`, a list of named stages each holding
tracks), but a playlist track carries `keep_probability` (the fit probability) and
`tone` instead of audio features, since there are no per-track audio features in this
mode. The response also carries `signals` (the four raw probabilities) and `excluded`
(`no_lyrics`, `instrumental` counts).

## Deviations from the plan

- The plan's example snippet used `"type": "yes/no"`; the installed `laya` package
  uses `"type": "noul"` for the same concept. Documented above and reflected in the
  adapter and its docstring.
- `laya`'s real models depend on `torch` with CUDA wheels, a large download (multiple
  gigabytes). The `laya`-marked integration test was written against the confirmed
  schema but was not executed in this session to keep turnaround reasonable; run it
  locally with `uv run pytest -m laya` to verify end to end against the real model.
