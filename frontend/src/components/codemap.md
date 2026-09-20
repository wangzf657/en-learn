# frontend/src/components/

<!-- Fixer: Fill in this section with architectural understanding -->

## Responsibility

Four reusable presentation components shared by the player views: the repeat-aloud scoring modal, the video subtitle overlay, the sentence-list panel, and the subtitle style/size picker.

## Design

All are `<script setup>` SFCs communicating via props + `defineEmits`; none call `api.js` except RepeatModal.

- **`RepeatModal.vue`** (~1400 lines) — full-screen `<Transition name="modal-fade">` dialog. Props `{ open, sentence }`, emits `close`.
  - Left 30% study area: word chips (`sentence.words[]`: `w`/`phonetic`/`note`) and segment chips (sentence split on `(?<=[.,!?;:…—])\s+`).
  - Right 70%: clickable sentence line (en + zh), editable repeat-text input, record button, rich result view.
  - Recording state machine `status: idle → starting → recording → scoring → result | error`, driven by the toggle controller from `startRecording()` (recorder.js); starting-phase cancel discards the take.
  - TTS via `configureUtterance` (tts.js): every chip/segment/sentence fills the input and speaks on click; `speakingKey` (`sentence`/`w-i`/`seg-i`/`custom`) tracks the active item; second click cancels via `speechSynthesis.cancel()`.
  - Rich score display: `overallScore` (mean of accuracy/fluency/completeness), 5-star mapping (score/20), grade labels (优秀→待加强), per-dimension bars, ASR standard-vs-read comparison, audio-quality badges (volume/clipping/noise/cut/too_short/empty_audio), per-word rows with accuracy color, word-type badges (`type` 0 多词/1 漏词/3 错词), stress ✓/✗, and phoneme chips colored by `phoneme_scores`.
  - Playback: hidden `<audio>` + blob URL (`URL.createObjectURL`), revoked on reset ("阅后即焚").
  - Window keydown: Space toggles recording unless typing in input/textarea/contenteditable or modal closed; `watch(open)` + `onBeforeUnmount` cleanup stops recorder/TTS/playback.
- **`SubtitleOverlay.vue`** — stateless; props `{ cues, currentTime, enabled, styleClass='sub-cinema', size='sub-size-lg' }`.
  - `currentCue` = first cue where `start <= t < end`; renders one `<p class="subtitle-cue">` keyed by text inside `<Transition name="cue" mode="out-in">`.
  - Entry-only animation — leave transition deliberately omitted so the `max-content` container never collapses mid-gap (documented in-source warning).
  - Styles are intentionally **global** (non-scoped): parent-supplied `styleClass` (`sub-clean` white / `sub-cinema` yellow display font / `sub-opaque` dark pill / `sub-off` hidden) and `size` (`sub-size-md/lg/xl` driving `--cue-size`/`--cue-size-cinema` variables, ≤640px fallbacks) must cross the scoped boundary. `aria-live="polite"`.
- **`SubtitlePanel.vue`** — props `{ title, sentences, currentIndex, emptyText, cardAction='seek' }`; emits `seek` (inline timestamp button, always) and the value of `cardAction` (`'seek'` | `'repeat'`) from the card body click.
  - Card shows `s.en`, optional `s.zh`, seek button labeled `m:ss` (local `formatTime`).
  - `watch(currentIndex)` + `nextTick` auto-scrolls `.sentence-card.active` into view (smooth, centered).
  - Named slot `actions` (`{ s, i }`) lets parents append per-sentence controls.
- **`SubtitleStylePicker.vue`** — two `<select>`s (style 清晰/影院/黑底/关闭; size 标准/大/特大) implementing `v-model` + `v-model:size` via `update:modelValue`/`update:size`.
  - Persists to localStorage keys `enlearn.subtitleStyle` / `enlearn.subtitleSize`; `loadPref`/`savePref` try/catch guards (invalid values fall back to prop defaults); `onMounted` restores saved values, emitting only when different.

## Flow

1. Play/LocalPlay pass sentence-derived cues + `currentTime` to SubtitleOverlay each tick → it recomputes the active cue.
2. SubtitlePanel card click → `emit('repeat', s)` → view's `openRepeat(s)` sets `{ repeatSentence, repeatOpen }` → RepeatModal opens, resets, speaks/fills from `sentence`.
3. Space in RepeatModal → `toggleRecording()` → `startRecording()` → stop → `scoringApi.score(blob, reference)` POST `/api/score` → result rendered.
4. Picker `@change` → emit + localStorage write → view ref updates `:style-class`/`:size` props on the overlay.

## Integration

- Consumed by `Play.vue` (all four) and `LocalPlay.vue` (overlay + panel + picker, no RepeatModal).
- RepeatModal depends on `utils/recorder.js`, `utils/tts.js`, `api.js#scoringApi`.
- SubtitleOverlay/Panel depend only on Vue; the `sub-*` class keys and localStorage keys are a shared contract with both views and SubtitleStylePicker.
