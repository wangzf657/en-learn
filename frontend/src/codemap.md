# frontend/src/

## Responsibility

Application skeleton: bootstrap + route table (`main.js`), persistent chrome and TTS warmup (`App.vue`), the single HTTP client for every backend call (`api.js`), and the global candy-cartoon design system (`style.css`).

## Design

- **`main.js`** — plain Composition-API bootstrap.
  - `createApp(App)` + `createRouter` with `createWebHistory`; five statically imported routes (no lazy loading): `/` Home, `/play/:date` Play with `props: true` (date param becomes a prop), `/local` LocalPlay, `/review` Review, `/admin` Admin.
  - Imports `style.css` globally; mounts to `#app`.
- **`App.vue`** — `<script setup>`.
  - Sticky glass app-bar: brand link + nav (日历 `/`, 自由播放 `/local`, 复习 `/review`, gear icon `/admin`); active state derived from `route.path`.
  - `<RouterView v-slot>` wraps the matched component in `<Transition name="page" mode="out-in">` (classes in style.css).
  - Only lifecycle logic: `onMounted` → `warmupTts({ voiceURI: loadTtsSettings().voiceURI })`, pre-heating the speech engine to kill first-speak latency.
  - No global keyboard handling here — shortcuts live per-view (Play: Space/Enter/F11; RepeatModal: Space; Review lightbox: Esc/arrows).
- **`api.js`** — hand-rolled fetch client, no axios. Private `request(path, {headers, ...options})` wraps `fetch('/api' + path)`.
  - JSON `Content-Type` by default, stripped for `FormData` bodies (browser sets the multipart boundary).
  - Non-OK → `Error` enriched with `.status` and `.detail` (parsed from the FastAPI `{detail}` body, fallback `statusText`); `204` → `null`; otherwise `res.json()`.
  - Exports five grouped namespaces:
    - `calendarApi.getMonth(month)`
    - `dayApi.get(date)` / `dayApi.checkin(date)`
    - `reviewApi.get()`
    - `adminApi`: library get/save, `importCourse`, course list/detail/delete, material delete/`setMaterialRead`, schedule create/get/`clearMonth`, `addDayMaterials`, `deleteDay`, `removeDayMaterial`
    - `scoringApi`: `score(audioBlob, reference)` (multipart `audio`+`reference`), `getScoring`, `saveScoring`
  - Media endpoints (`/materials/:id/stream|srt`) intentionally bypass `api.js` — views use raw URLs in `<video src>`/`fetch`.
- **`style.css`** — ~780 lines, zero dependencies, all tokens as `:root` CSS variables.
  - Candy palette (`--blue/--yellow/.../--pink/--purple/--cyan` + `-bg` variants), neutrals, layout (`--layout-width/max`, `--appbar-h` consumed by Play's fixed-screen height), shadows, radii, local font stacks (`--font-display` Comic Sans…, no webfonts), bounce easings, shared gradients.
  - Base resets + reusable classes: `.btn` variants, `.icon-btn`, `.card`, `.page`, `.badge-*`, `.form-field`, `.table-wrap`, `.error-detail`, `.sr-only`, `.empty-state`, `.mascot`.
  - The `page` transition classes plus shared `@keyframes` (`pulse`, `wiggle`, `float-y`, `pop-in`, `star-pop`, `spin`, `confetti-fall`, …) used by scoped styles across views/components; mobile breakpoint + `prefers-reduced-motion`.
  - Subtitle styling is NOT here — it lives in SubtitleOverlay.vue.

## Flow

1. `index.html` → `main.js` → router matches URL → `App.vue` renders app-bar + transitioned view.
2. Views call e.g. `dayApi.get(date)` → `fetch('/api/day/…')` → Vite proxy or mock plugin → backend; errors surface as `e.detail` strings rendered by the view.
3. RepeatModal → `scoringApi.score(blob, reference)` → multipart POST `/api/score` → scoring result object.
4. App start: `warmupTts` fires a zero-volume utterance with the persisted voice from localStorage (`enlearn:tts`).

## Integration

- `main.js` mounts all of `views/` and imports `App.vue` + `style.css`.
- `App.vue` depends on `utils/tts.js` and vue-router.
- `api.js` is the sole backend gateway, consumed by every view and `RepeatModal.vue`; its contract is mirrored by `mockApiPlugin.js` and `backend/main.py`.
- `style.css` variables/classes/keyframes are consumed by every `.vue` file.
