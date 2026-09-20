# frontend/

## Responsibility

Project layer for the Vue 3 SPA: build/dev tooling, test setup, the in-memory mock API, the offline smoke script, and the HTML entry — everything `src/` needs to run without the Python backend.

## Design

- **`package.json`** — runtime: `vue ^3.5.42`, `vue-router ^5.3.1`; dev: `vite ^8.3.0`, `@vitejs/plugin-vue ^6.0.8`, `vitest ^5.0.0`, `@vue/test-utils ^2.5.0`, `happy-dom ^20.14.5`.
  - Scripts: `dev` (Vite server), `build` (`vite build` → `dist/`), `preview`, `test` (`vitest run`). No lint/format tooling.
- **`vite.config.js`**
  - Plugins: `vue()` plus conditionally `mockApiPlugin()`; mock switch is `process.env.MOCK === '1' | 'true'`.
  - Mock off → `server.proxy` forwards `/api` → `http://127.0.0.1:8420` (`changeOrigin: true`); mock on → proxy removed so the plugin middleware sees `/api` first.
  - Dev port is Vite's default 5173 (not overridden).
- **`vitest.config.js`** — separate config: vue plugin, `environment: 'happy-dom'`, `globals: true`; no mock plugin, so component tests stub `api.js`/fetch themselves.
- **`mockApiPlugin.js`** — Vite plugin whose only hook is `configureServer`.
  - Installs one connect middleware via `server.middlewares.use('/api', ...)`; mounted at the `/api` prefix, so regexes match `req.url` without it.
  - Module-level mutable state: `courses`, `materials` (with `dates[]`, `read`, `readAt`), `libraryRoot`, `scoringConfig`.
  - Covers the full REST surface via regex dispatch + `sendJson`/`sendText`/`sendBinary`/`readBody` helpers; errors are FastAPI-shaped `{ detail }`.
  - `/api/materials/:id/stream` serves `public/mock/empty.mp4` (28-byte stub); `/srt` returns a fixed SRT string; all materials share one rich `sampleSubtitle`.
  - `/score` parses multipart just enough to extract `reference`, returns deterministic scores (word #2 forced low to demo error badges).
- **`smoke-dev.mjs`** — node smoke test: sets `MOCK=1`, boots Vite programmatically (`createServer`, `logLevel: 'silent'`), `fetch`es every mocked endpoint with expectation predicates, checks page shells (`/`, `/play/2026-09-14`, `/local`), closes the server, exits 1 on any failure.
- **`index.html`** — `lang="zh-CN"`, favicon `/favicon.svg`, `#app` mount div, module script `/src/main.js`.
- **`public/`** — `favicon.svg` (referenced by index.html), `icons.svg` (SVG symbol sprite, currently unreferenced by `src/` — leftover scaffolding), `mock/empty.mp4` (mock stream body).

## Flow

1. `npm run dev` → Vite starts on 5173.
2. `MOCK` unset → browser calls `/api/...` → proxy → FastAPI on 8420.
3. `MOCK=1` (or `node smoke-dev.mjs`) → mock middleware intercepts `/api/*` and answers from in-memory state.
4. `POST /api/admin/courses/import` mutates mock state (`folder` containing "fail" → 422), so later `GET /api/admin/courses` reflects it — stateful within one dev session.
5. `npm run build` emits static `dist/`, hosted by the FastAPI backend in production.

## Integration

- Consumed by the whole `src/` app, which only ever talks to same-origin `/api` — never `127.0.0.1:8420` directly.
- `mockApiPlugin.js` mirrors the backend contract in `backend/main.py` (import, schedule, day CRUD, checkin, scoring, review); `smoke-dev.mjs` validates it.
- `public/mock/empty.mp4` is consumed only by the mock stream endpoint; root `build.bat` drives `npm run build` + PyInstaller packaging.
- `vitest.config.js` is independent of `vite.config.js`.
