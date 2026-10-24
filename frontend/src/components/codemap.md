# frontend/src/components/

<!-- Fixer: Fill in this section with architectural understanding -->

## Responsibility

Four reusable presentation components shared by the player views: the repeat-aloud scoring modal, the video subtitle overlay, the V2.0 dual-tab practice panel, and the subtitle style picker.

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
- **`SubtitleOverlay.vue`** — stateless; props `{ cues, currentTime, enabled, styleClass='sub-clean', size='sub-size-lg' }`; renders cue text via `v-html` so karaoke `<font>` highlight works, keyed on tag-stripped text (highlight moves patch in place; line changes replay the enter transition).
  - `currentCue` = first cue where `start <= t < end`; renders one `<p class="subtitle-cue">` keyed by text inside `<Transition name="cue" mode="out-in">`.
  - Entry-only animation — leave transition deliberately omitted so the `max-content` container never collapses mid-gap (documented in-source warning).
  - Styles are intentionally **global** (non-scoped): parent-supplied `styleClass` (`sub-clean` white / `sub-cinema` yellow display font / `sub-opaque` dark pill / `sub-off` hidden) and `size` (`sub-size-md/lg/xl` driving `--cue-size`/`--cue-size-cinema` variables, ≤640px fallbacks) must cross the scoped boundary. `aria-live="polite"`.
- **`PracticePanel.vue`** — V2.0 带学练习面板. Props `{ practice }` (the material's teaching-JSON object); emits `seek` (sentence timestamp button) and `repeat` (word chip / sentence card / child dialogue line).
  - Two internal tabs: 跟读练习 (key-word chips, key-sentence cards, parent-child dialogue cards) and 家长带学 (goal card + before/during/after/tips groups, read-only).
  - Sentence cards reuse the old `.sentence-card` look: card click = `emit('repeat', s)` (whole-sentence repeat), inline `.seek-btn` = `emit('seek', s)`.
  - Dialogue lines click-to-speak via `tts.js#speak` (jsdom-safe no-op); `speakingKey` highlights the line being read; only `speaker === 'child'` lines get a 跟读 mini-button.
  - Word chip payloads synthesize `{ en: w.w, zh, words: [{w, note}]? }` — RepeatModal accepts any such object.
  - Empty states: no boards → "本集暂无练习内容"; legacy full-script data (sentences only) still renders in the sentences block, guide tab shows its empty state.
- **`SubtitleStylePicker.vue`** — two `<select>`s (style 清晰/影院/黑底/关闭; size 标准/大/特大) implementing `v-model` + `v-model:size` via `update:modelValue`/`update:size`.
  - Persists to localStorage keys `enlearn.subtitleStyle` / `enlearn.subtitleSize`; `loadPref`/`savePref` try/catch guards (invalid values fall back to prop defaults); `onMounted` restores saved values, emitting only when different.

## Flow

1. Play/LocalPlay pass srt-derived cues + `currentTime` to SubtitleOverlay each tick → it recomputes the active cue.
2. PracticePanel interactions → `emit('repeat', payload)` → view's `openRepeat(s)` sets `{ repeatSentence, repeatOpen }` (pausing the video) → RepeatModal opens, resets, speaks/fills from `sentence`; `emit('seek', s)` → view seeks `video.currentTime = s.start` and plays.
3. Space in RepeatModal → `toggleRecording()` → `startRecording()` → stop → `scoringApi.score(blob, reference)` POST `/api/score` → result rendered.
4. Picker `@change` → emit + localStorage write → view ref updates `:style-class`/`:size` props on the overlay.

## Integration

- Consumed by `Play.vue` (all four) and `LocalPlay.vue` (all four — it gained RepeatModal in V2.0).
- RepeatModal depends on `utils/recorder.js`, `utils/tts.js`, `api.js#scoringApi`; PracticePanel depends on `utils/tts.js#speak`.
- SubtitleOverlay/PracticePanel otherwise depend only on Vue; the `sub-*` class keys and localStorage keys are a shared contract with both views and SubtitleStylePicker.
