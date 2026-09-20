# backend/echoic/providers/

## Responsibility

Pluggable scoring backends: the `ScoringProvider` protocol and name registry (`base.py`), plus one implementation per evaluation API — `mock` (fixed-score fake) and `unisound` (Unisound edu-cloud HTTP API).

## Design

- **ABC protocol** (`base.py`): a subclass defines the class attribute `name` (registry key referenced by admin config), receives read-only `options` via `__init__(options)`, and implements `score(recording_path, reference_text, language) -> ScoringResult`. Stated contract: raise exceptions with readable causes on network/auth/param errors; unspoken reference words = low score, not an error; vendor-original scores, no re-scaling.
- **Module-level registry**: `_REGISTRY: dict[str, type[ScoringProvider]]`; `register_provider(cls)` stores by `cls.name` (idempotent, same-name overwrite for test substitution) and returns the class unchanged; `available_providers()` returns sorted keys; `get_provider(name, options)` instantiates by name, unknown name ⇒ `ValueError` with the option list.
- **Registration at import time** (`providers/__init__.py`): one line per provider (`register_provider(MockProvider)`, `register_provider(UnisoundProvider)`), then re-exported by `echoic/__init__.py`.
- **mock.py**: deterministic fake — 82.5/78.0/90.0 totals, every word 85.0 with phoneme scores [85, 80, 90]; never reads the audio, zero network. For frontend integration and smoke tests; values match the design-doc contract sample.
- **unisound.py** (live provider, `requests` HTTP) — hard constraints for the sacalleval API:
  - multipart field order **text → mode → voice** (satisfied naturally: `requests` sends `data=` before `files=`)
  - auth headers: `appkey: {AppKey}@{AppSecret}` (no signature) + `session-id` (uuid4, ≤ 64 chars); optional `score-coefficient` (0.6–1.9, looser grading when larger); `X-EngineType: oral.zh_CH` when `language == "zh"` (mode must then be E)
  - WAV and pcm both POST to `{base_url}/pcm` (default `http://edu.hivoice.cn/eval`, overridable) — zero transcoding
  - word/phoneme scores arrive on a 0–10 scale → ×10 normalized to 0–100; line-level `pronunciation`/`fluency`/`integrity` are already 0–100
  - multi-line reference: the three totals are per-line means (`_parse_response`)
  - word filter: keep only `type` ∈ {0,1,2,3}; silence/repeat/punctuation/unknown-word entries dropped; `stress` from `StressOfWord` (−1 when absent/invalid); `audiocheck` → `AudioQuality` flags, tolerant of list/object shapes and key-case variants (`_AUDIO_FLAGS`)
  - error mapping: known `errcode`s → readable reasons via `_ERRCODES`; non-200, non-JSON, or `errcode != 0` ⇒ `RuntimeError`; request timeout `max(10, 3 + (n_words − 10) / 5)` s
  - options: `appkey`/`secret` required (`ValueError` if missing), `base_url` override, `mode` default `"E"` (word/sentence read-aloud with per-word/per-phoneme scores; passage mode is `C`)

## Flow

1. `get_provider("unisound", options)` → `UnisoundProvider(options)`.
2. `score()`: validate `appkey`/`secret` → build headers → open the WAV → `requests.post(base_url + "/pcm", data={"text", "mode"}, files={"voice"})`.
3. Response: `errcode != 0` or HTTP ≠ 200 ⇒ `RuntimeError` (host maps to 500).
4. `_parse_response()` → ×10 normalization of word/phoneme scores, per-line means for totals, ASR/audiocheck diagnostics → `ScoringResult`.

## Integration

- **Upstream**: `echoic/__init__.py` imports the registry and concrete classes; nothing here imports the host.
- **Downstream**: `unisound` calls the Unisound edu-cloud HTTP endpoint; `mock` has no dependencies. Per-provider SDK deps would go in `requirements.txt`.
- **Extension**: new provider = one `ScoringProvider` subclass file + one `register_provider(...)` line in `providers/__init__.py`.
