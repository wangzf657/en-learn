# frontend/src/views/

<!-- Fixer: Fill in this section with architectural understanding -->

## Responsibility

The five route-level pages: learning calendar (Home), scheduled-day player (Play), free course-library player (LocalPlay), review center (Review), and the administration console (Admin).

## Design

All `<script setup>` Composition API; each owns its fetch lifecycle, local UI state, and scoped styles. Views are wire-together layers — data access goes through `api.js`; media URLs are raw `/api/materials/:id/stream|srt` paths fed to `<video>`/`fetch`.

- **`Home.vue`** (`/`)
  - Month calendar: `watchEffect` on `{year, month}` refs → `calendarApi.getMonth(formatMonth(...))`; `dayMap` keyed by `date` for O(1) cell lookup.
  - Grid cells from `getMonthGrid` (date.js, Monday-first with `null` blanks); hero shows `checkedCount`.
  - Cell states `has-video`/`checked`/`is-today`; clicking a day with `materialId` routes to `/play/:date`; empty month links to `/admin`.
- **`Play.vue`** (`/play/:date`, `props: true`) — fixed one-screen player.
  - `onMounted` sets `document.documentElement/body.style.overflow = 'hidden'` (restored on unmount); height `calc(100svh - var(--appbar-h))`.
  - Loads `dayApi.get(date)`; `currentMaterialIndex` switches day materials (chips, role=tablist); sentences come from `material.subtitle.sentences`.
  - `loadCuesFallback()` fetches `srtUrl` + `parseSrt` only when sentences are empty; monotonic `srtReqId` discards stale responses. `cues` prefers in-memory sentences over srt cues.
  - Custom controls (play, volume, draggable progress, rate select, fullscreen on `layoutRef`) mirror `<video>` events into refs; `currentIndex` maps time→sentence for panel highlighting.
  - **Global shortcuts** (window keydown; skipped when RepeatModal is open or target is editable; `preventDefault` also for focused buttons): `Space` = play/pause, `Enter` = collapse/expand the sentence drawer (`subtitleOpen`; auto-collapsed on entering fullscreen), `F11` = toggleFullscreen (Fullscreen API + `fullscreenchange` listener).
  - Checkin button → `dayApi.checkin(date)` → toast + confetti.
  - Composes all four components: SubtitleOverlay/StylePicker in the video section, SubtitlePanel (`card-action="repeat"`) + RepeatModal in the drawer.
- **`LocalPlay.vue`** (`/local`) — free playback.
  - `adminApi.listCourses()` → accordion sidebar; expanding a course lazily `adminApi.getCourse(id)` into a `courseMaterials` cache.
  - `playMaterial(material)` sets `video.src = /api/materials/:id/stream`, resets time, and falls back to `/api/materials/:id/srt` + `parseSrt` (same stale-response guard) when no embedded sentences.
  - Reuses SubtitleOverlay/StylePicker/SubtitlePanel (`card-action="seek"` — card click seeks to the sentence) but has **no RepeatModal and no keyboard shortcuts**; fullscreen targets the stage element.
- **`Review.vue`** (`/review`)
  - `reviewApi.get()` once on mount → `groups` (course-level `kind:'course'` + per-material groups; `files[]` with `{name, url, kind: 'image'|'pdf'}`).
  - Three-level in-page navigation (no sub-routes): `selectedCourseId` → `selectedGroupKey` → lightbox; `courseSections` computed groups by `courseId`.
  - Files render as lazy `<img>` or `<iframe>` for PDF; lightbox cycles with Esc / ← / → via a window keydown bound while mounted.
- **`Admin.vue`** (`/admin`, largest view) — three `v-show` tabs (`activeTab`: `settings` 通用设置, `courses` 课程管理, `checkin` 打卡管理).
  - Settings: library root (`adminApi.getLibrary/saveLibrary`); scoring config (`scoringApi.getScoring/saveScoring`: provider select + options, `SCORING_DEFAULTS` mirrored from unisound.py, AppKey/Secret validation, mock clears options); TTS voice/rate (`listEnglishVoices` + `voiceschanged` listener + `preview`/`saveTtsSettings`, re-warming on change).
  - Courses: `adminApi.importCourse` (result carries `materials[].updated` + `skipped[]`), expandable course list with lazy `getCourse` detail cache, material table paginated 10/page, read toggle (`setMaterialRead`), deletes behind `confirm()`.
  - Checkin: schedule form (`createSchedule(courseId, dateFrom, dateTo)`); month calendar from `calendarCells` computed (Monday-first, per-date materials from `adminApi.getSchedule(month)`, watched for reload); per-day detail with add-materials picker (`addDayMaterials`), `removeDayMaterial`, `clearDay`, `clearMonth`; every mutation re-fetches `loadScheduleDays()` + `loadCourses()`.

## Flow

1. Home: month change → `calendarApi.getMonth` → `days[]` → dayMap → cell click → `router.push('/play/2026-09-14')`.
2. Play: `dayApi.get(date)` → materials + subtitles → `<video>` streams `/api/materials/:id/stream` → `timeupdate` drives `currentTime` → overlay cue + panel highlight → card click `repeat` → RepeatModal → `scoringApi.score` → `/api/score`.
3. Play: checkin button → `dayApi.checkin(date)` → backend marks the day checked and its materials read.
4. Admin: import/schedule/ day CRUD → refresh via `loadCourses` + `loadScheduleDays`; schedule POST makes the backend distribute materials evenly across dates.

## Integration

- Registered in `main.js`'s route table; `Play` receives `:date` as a prop.
- All consume `api.js`; Play/LocalPlay additionally use `utils/srt.js`, Admin uses `utils/tts.js`, Home uses `utils/date.js`.
- Component usage: Play → Overlay+Picker+Panel+RepeatModal; LocalPlay → Overlay+Picker+Panel; Review/Admin use none.
