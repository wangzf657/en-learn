# backend/

## Responsibility

Host backend / service layer: a single-file FastAPI app (`main.py`) over SQLite (`data/enlearn.db`) providing course → material management, day-scheduling and check-ins, review-center file serving, generic settings (library root, scoring provider), and static hosting of the built SPA on `127.0.0.1:8420`.

## Design

- **Single-module monolith** with sectioned route groups (consumer, review center, settings, course admin, schedule admin, scoring); catch-all SPA route registered last.
- **Persistence**: raw `sqlite3`, per-request connection factory `db()` (row_factory = `sqlite3.Row`), transactions via `with closing(db()) as conn, conn:`. Tables: `courses`, `materials` (both `UNIQUE rel_path`), `day_materials` (PK `(date, material_id)`), `checkins` (PK `date`).
- **Migration runner**: `SCHEMA_VERSION` + `MIGRATIONS` (list of `(target_version, SQL)`) stamped with `PRAGMA user_version`. `init_db()`: refuses startup if the data file is newer than the program (`sys.exit`); a v0 DB (fresh or legacy unstamped) just runs the idempotent `SCHEMA` (all `CREATE TABLE IF NOT EXISTS`) and drops obsolete `books`/`day_books`; pending migrations first back up to `data/enlearn.db.bak`, then execute each atomically as `BEGIN;<sql>;PRAGMA user_version=n;COMMIT;`.
- **File-based config, re-read every request** (changes take effect instantly, corrupt/missing falls back): `data/library.json` → `{"root": ""}`; `data/scoring.json` → `{"provider": "mock", "options": {}}`. Writes are atomic (`tempfile` + `os.replace`).
- **Relative-path media**: DB stores only `rel_path` under the library root; moving the library = editing `library.json`. Unconfigured root ⇒ 422 on import/stream/srt/review-file.
- **Idempotency via natural keys**: re-import upserts by `rel_path` (stable ids, disappeared files kept); `INSERT OR IGNORE` on `day_materials` and `checkins` makes overlapping schedules / repeated check-ins no-ops.
- **Read state machine**: `materials.read_at` only transitions NULL → timestamp (`PUT /api/admin/materials/{mid}/read` fills NULL; first check-in stamps only still-unread materials, manual timestamps preserved); `read: false` resets to NULL.
- **Natural sort**: `natural_key()` splits digit runs (`re.split(r"(\d+)")`); used for import order, per-day material ordering, review grouping, title prefix stripping.
- **Frozen-aware paths** (PyInstaller): `BASE_DIR` = exe dir (writable `data/`), `ASSET_DIR` = `sys._MEIPASS` (read-only `frontend/dist`); in dev both resolve to the repo root.

## Flow

1. Startup: `init_db()` → auto-open browser after 1.5 s unless `ENLEARN_NO_BROWSER=1` → `uvicorn` on `127.0.0.1:8420`.
2. Import `POST /api/admin/courses/import {folder}`: `resolve_import_folder()` (root configured? folder under root?) → direct-child `*.mp4` only (non-recursive), natural-sorted → sibling `stem/stem.json` subtitle validated by `normalize_subtitle()` (`sentences[{start,end,en}]`; invalid ⇒ `skipped`, not inserted) → title strips `^\d{1,3}[._-]\s*` → course upsert by `rel_path` prefix, material upsert by `rel_path`.
3. Schedule `POST /api/admin/schedule {courseId,dateFrom,dateTo}`: expand date range (may cross months) → materials natural-sorted → if n ≥ d divide evenly (`divmod`, first `extra` days get +1), else first n days get 1, rest left empty → `INSERT OR IGNORE` → returns `added` + per-day `materialIds`.
4. Consume: `GET /api/calendar?month=` groups `day_materials` with a checkin LEFT JOIN per date; `GET /api/day/{date}` returns materials with `videoUrl`/`srtUrl` (srt existence probed on disk) + subtitle JSON; `POST /api/day/{date}/checkin` is per-day idempotent and on first insert marks that day's unread materials read.
5. Media: `GET /api/materials/{mid}/stream` → `FileResponse` (Starlette answers Range requests with 206); `GET /api/materials/{mid}/srt` reads `root/<parent>/<stem>/<stem>.srt` (utf-8-sig) as text.
6. Review: `GET /api/review` scans course-level (`root/<course rel>/<course name>`) and material-level (`root/<material parent>/<stem>`) folders of read items for images/PDF (PDF first, then natural order); `GET /api/review/file/{courseId}/{materialId}/{filename}` (`materialId=0` = course level) serves via `FileResponse` with a path-traversal guard (no `/`/`\`, resolved parent must equal the folder).
7. Scoring: `POST /api/score` (multipart `audio` + `reference` form field) → `scoring_config()` → temp `.wav` → `echoic.score_recording(provider, options)` → `ValueError`/`RuntimeError` mapped to 500 → `result.model_dump()`; temp file always unlinked. `GET/PUT /api/admin/scoring` validates the provider against `available_providers()` (422 if unknown) and rewrites `scoring.json`.
8. Deletion cascades: course/material delete removes their `day_materials` then `clean_orphan_checkins()` drops check-ins on days left empty; `DELETE /api/admin/day/{date}` and `DELETE /api/admin/schedule?month=` clear schedules + matching check-ins; per-material day removal (`DELETE /api/admin/day/{date}/materials/{mid}`) 422s if not scheduled.
9. SPA catch-all `GET /{full_path:path}`: rejects `api/*` with 404, serves `dist` assets (prefix-checked), falls back to `index.html`, or returns a "frontend not built" stub.

## Integration

- **Upstream**: Vue SPA built to `frontend/dist` (served here; Vite dev proxies `/api` to :8420; CORS `allow_origins=["*"]` for dev).
- **Downstream**: `echoic` package (`score_recording`, `available_providers`) for scoring, configured by `data/scoring.json` (Admin-editable).
- **Data files**: `data/enlearn.db`, `data/library.json`, `data/scoring.json`; media files live on disk under the library root, never in the DB.
- **Packaging**: `build.bat` → PyInstaller onefile; `requirements.txt`: fastapi, uvicorn[standard], python-multipart, requests, pillow (build-only icon), pyinstaller.
- **Verification**: `backend/smoke_test.py` self-hosts the server and exercises all API families (import/schedule/read/checkin/stream/srt/score).
