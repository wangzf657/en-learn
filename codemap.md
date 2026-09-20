# Repository Atlas: en-learn

## Project Responsibility

A single-machine, self-hosted English-learning application (no login, no cloud): course videos are imported from a local media library, scheduled onto calendar days, played with bilingual subtitles and read-aloud pronunciation scoring, and reviewed through image/PDF materials. The repo is one product in two deployable parts plus a packaging script:

- **Host backend** — single-file FastAPI + SQLite that manages courses/materials/schedules/check-ins, streams video, serves review files, proxies pronunciation scoring, and hosts the built SPA.
- **SPA frontend** — Vue 3 (Vite + vue-router + vitest) talking only to same-origin `/api`; runs standalone against an in-memory mock API during development.
- **Desktop release** — `build.bat` produces a one-file PyInstaller `EnLearn.exe` (frontend `dist/` bundled inside).

## System Entry Points

- `backend/main.py` — FastAPI application, uvicorn on `127.0.0.1:8420`, migration runner at startup, auto-opens browser (set `ENLEARN_NO_BROWSER=1` to suppress).
- `frontend/index.html` → `frontend/src/main.js` — SPA bootstrap and route table; `npm run dev` serves on :5173 and proxies `/api` to :8420 (`MOCK=1` switches to the in-memory mock plugin).
- `build.bat` — one-shot release build (pip install → `npm run build` → PyInstaller onefile → `release/EnLearn.exe`).
- Runtime data (outside git): `data/enlearn.db`, `data/library.json` (media-library root), `data/scoring.json` (scoring provider + credentials).

## End-to-End Data Flow

1. **Admin** sets library root → imports a course folder (direct-child `*.mp4` + sibling JSON subtitle) → backend upserts by `rel_path` natural key.
2. **Admin** schedules a course over a date range → backend evenly distributes materials across days (`day_materials`).
3. **Learner** opens a day (`/play/:date`) → video streams via HTTP Range (206), subtitles render from embedded JSON or fetched SRT.
4. **Repeat modal** records browser-encoded 16 kHz/16-bit/mono WAV → `POST /api/score` → `echoic` facade → registered provider (`mock`/`unisound`) → 0–100 normalized scores.
5. **Check-in** marks the day and stamps its still-unread materials; read items then surface their image/PDF sibling files in the review center.

## Repository Directory Map

| Directory | Responsibility Summary | Detailed Map |
|-----------|------------------------|--------------|
| `backend/` | Host service layer: single-file FastAPI + SQLite monolith — import, scheduling, check-ins, Range streaming/SRT, review file serving, scoring proxy, migration runner, SPA hosting. | [View Map](backend/codemap.md) |
| `backend/echoic/` | Pronunciation-scoring integration shell: facade `score_recording()` + provider registry, pydantic 0–100 result contract, error contract. | [View Map](backend/echoic/codemap.md) |
| `backend/echoic/providers/` | Pluggable scoring backends: `ScoringProvider` ABC + name registry, `mock` fake and `unisound` cloud API (multipart order, ×10 normalization, auth headers). | [View Map](backend/echoic/providers/codemap.md) |
| `frontend/` | SPA engineering layer: Vite/vitest configs, in-memory mock API Vite plugin, offline smoke script, HTML entry. | [View Map](frontend/codemap.md) |
| `frontend/src/` | App skeleton: router bootstrap, persistent app bar + TTS warmup, the sole fetch client `api.js`, global design-system CSS. | [View Map](frontend/src/codemap.md) |
| `frontend/src/components/` | Four player components: RepeatModal (record/score state machine), SubtitleOverlay, SubtitlePanel, SubtitleStylePicker. | [View Map](frontend/src/components/codemap.md) |
| `frontend/src/views/` | Five route pages: Home calendar, fixed-screen Play, free LocalPlay, Review center, three-tab Admin console. | [View Map](frontend/src/views/codemap.md) |
| `frontend/src/utils/` | Dependency-free utilities: Monday-first calendar math, raw-PCM WAV recorder, SRT parser, speechSynthesis wrapper. | [View Map](frontend/src/utils/codemap.md) |

## Root Assets

- `README.md` — project overview.
- `AGENTS.md` — AI agent repo guide (architecture notes, gotchas, verification commands).
- `build.bat` — release build entry point.
- `opencode.json` — OpenCode tooling configuration.
- `docs/design.md` — V1.0 source-of-truth design/API contract; `docs/v1.1.0.md` — unimplemented iteration notes (excluded from code mapping).
- `.agents/skills/srt-to-json/` — local skill for producing enriched teaching subtitle JSON (tooling, not application code; excluded from mapping).

## Verification

- Backend API smoke: `backend\.venv\Scripts\python.exe backend\smoke_test.py` (rebuilds `data/enlearn.db` — never run against real data).
- Frontend unit tests: `npm test` in `frontend/` (vitest).
- Frontend mock smoke: `node smoke-dev.mjs` in `frontend/` (self-sets `MOCK=1`, no backend needed).
