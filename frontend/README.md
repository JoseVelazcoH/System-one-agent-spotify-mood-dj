# Laya Mood DJ frontend

## Running locally

The backend uses a Spotify OAuth flow with an httpOnly session cookie, and Spotify's
redirect target must match a fixed host. Because of this, the frontend MUST be served
at `http://127.0.0.1:5173` (not `localhost:5173`):

1. Copy `.env.example` to `.env` and set `VITE_API_BASE_URL` (defaults to
   `http://127.0.0.1:8000`, matching the backend's default host/port).
2. Run `npm install` then `npm run dev`. The Vite dev server is configured
   (`vite.config.ts`) to bind to `127.0.0.1:5173`.
3. Start the backend with `uv run uvicorn mood_dj.api.main:app --host 127.0.0.1 --port 8000`
   from the `backend/` directory, with `FRONTEND_URL=http://127.0.0.1:5173` so the
   OAuth callback redirects back to the dev server, and Spotify's registered redirect
   URI set to `http://127.0.0.1:8000/auth/callback`.
4. Open `http://127.0.0.1:5173` in the browser (not `localhost`), since the session
   cookie and CORS origin are both scoped to `127.0.0.1`.

## Modes

- **My playlists**: connect your Spotify account, pick a playlist, wait for lyrics
  analysis to finish, then describe your mood to get a personalized playlist built
  from your own tracks.
- **Discover**: the original flow, recommending tracks from the bundled dataset
  without requiring Spotify login.

---

# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
