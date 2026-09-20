# frontend/src/utils/

<!-- Fixer: Fill in this section with architectural understanding -->

## Responsibility

Four dependency-free pure utility modules: calendar date math, browser WAV recording, SRT parsing, and a speechSynthesis wrapper with persisted voice settings.

## Design

- **`date.js`** — pure functions over `YYYY-MM-DD` strings.
  - `pad(n)` two-digit zero-fill; `formatMonth(year, month)` → `YYYY-MM` (the `?month=` query format).
  - `dateKey(date)` / `todayKey()` build local-time date keys (no UTC drift).
  - `getMonthGrid(year, month)` returns Monday-first cells (`(first.getDay() + 6) % 7` leading offset), `YYYY-MM-DD` strings padded to whole weeks with `null`.
  - `addMonth(year, month, delta)` normalizes overflow via `new Date(year, m, 1)`.
- **`recorder.js`** — records raw PCM instead of MediaRecorder/webm: candidate cloud scoring APIs reject webm, and WAV means zero server-side transcode and no ffmpeg dependency.
  - `startRecording()` → `getUserMedia({audio:true})` with friendly errors for permission/device failure → `new AudioContext({ sampleRate: 16000 })` → `createMediaStreamSource` → `createScriptProcessor(4096, 1, 1)` pushing `Float32Array` channel chunks.
  - Graph routes through a **zero-gain node to `destination`** (required on Chrome or the processor never fires; silent to the user).
  - Returns a controller whose `stop()` disconnects, stops tracks, closes the context, and resolves a `Blob`.
  - `pcmToWav(chunks)` hand-writes a 44-byte RIFF header — mono (1 channel), 16000 Hz, 16-bit PCM — then clamps samples to [-1, 1] and converts to little-endian `Int16`.
- **`srt.js`** — `parseSrt(text)` → `[{ start, end, text }]` in seconds.
  - Strips BOM, normalizes CRLF/CR; splits blocks on blank lines; tolerates an optional numeric index line.
  - Parses `HH:MM:SS[,.]mmm --> ...` (comma or dot decimal separator); joins multi-line cue text with `\n`.
  - Rejects blocks without valid times and cues where `end <= start`.
- **`tts.js`** — config singleton in localStorage key **`enlearn:tts`** (`{ voiceURI, rate }`, default rate 0.9, `LANG 'en-US'`).
  - `loadTtsSettings` / `saveTtsSettings` (merge patch, try/catch for privacy mode).
  - `listEnglishVoices()` filters `getVoices()` by `lang` prefix `en`, returning `[]` safely under jsdom; `resolveVoice(voiceURI)`; `configureUtterance(utter)` applies stored voice+rate (caller owns `onend/onerror`).
  - `preview(text, {voiceURI, rate})` for the Admin test-listen — explicit params, not persisted.
  - `warmupTts({voiceURI})` calls `synth.resume()` then speaks a **zero-volume one-space utterance**: pre-initializes the engine and works around Chrome going mute after idle.
  - Note: the voice list itself loads asynchronously (`voiceschanged` event); this module stays event-free — consumers (App.vue, Admin.vue) re-read/warm on that event.

## Flow

1. Recording: RepeatModal "record" → `startRecording()` → mic streams into `chunks` → "stop" → `stop()` → `pcmToWav` → WAV blob → `scoringApi.score(blob, reference)` multipart POST `/api/score`.
2. Subtitles: Play/LocalPlay `fetch('/api/materials/:id/srt')` → `parseSrt(text)` → cues shaped like embedded `subtitle.sentences` for SubtitleOverlay.
3. TTS: app mount → `warmupTts` with saved voice; RepeatModal clicks → `new SpeechSynthesisUtterance` + `configureUtterance` → speak; Admin → `preview` + `saveTtsSettings`.
4. Dates: Home renders `getMonthGrid` + `formatMonth` → `calendarApi.getMonth`; `todayKey()` highlights today.

## Integration

- `recorder.js` → consumed only by `components/RepeatModal.vue`; verified by `src/tests/recorder.spec.js`.
- `srt.js` → consumed by `views/Play.vue` and `views/LocalPlay.vue`; tested in `srt.spec.js`.
- `tts.js` → consumed by `App.vue` (warmup), `components/RepeatModal.vue` (`configureUtterance`), `views/Admin.vue` (settings UI); tested in `subtitle-tts.spec.js`.
- `date.js` → consumed by `views/Home.vue` only; no dedicated spec (covered via calendar.spec.js).
- No module imports another; all are side-effect-free ES modules with named exports.
