# backend/echoic/

## Responsibility

Pronunciation-scoring integration shell: a provider-agnostic library exposing one entry point, `score_recording()`, which dispatches through a registry to concrete cloud speech-evaluation APIs (`mock`, `unisound`).

## Design

- **Facade + provider/strategy registry**: host code only knows provider *names* plus an options dict; `score_recording(recording_path, reference_text, provider="mock", options=None, language=None)` resolves the class via `get_provider(name, options)` and delegates. Adding or swapping a backend never touches the facade.
- **Pydantic contract, one scale end-to-end**: `ScoringResult` (accuracy/fluency/completeness 0–100, `word_scores`, ASR diagnostics `sample`/`usertext`, optional `audio_quality`) and `WordScore` (0–100 word/phoneme scores, expected vs actual phonemes, word `type` 0 multi/1 missing/2 normal/3 wrong, `stress` -1/0/1), plus `AudioQuality` (volume/clipping/noise/cut/too_short/empty flags). Vendor quirks (e.g. 0–10 scales) are normalized *inside providers*, so everything above sees a single unit.
- **No score transformation above the provider**: values are vendor-original calibrated scores; scores from different providers are explicitly not comparable.
- **Error contract**: configuration/unknown-provider problems raise `ValueError`; network/auth/HTTP problems raise `RuntimeError` with a readable cause — the host maps both to 500. A reference word simply not spoken is a low score, never an error.
- **Dependency direction**: `__init__.py` re-exports from `.providers` and `.schemas`; providers import only `..schemas` — no back-references to the host.

## Flow

1. Host (`main.py` `POST /api/score`) reads `data/scoring.json` per request for provider name + options.
2. `score_recording(path, reference, provider, options)` → `get_provider(name, options)`; unknown name ⇒ `ValueError` listing `available_providers()`.
3. `provider.score(recording_path, reference_text, language)` → `ScoringResult` (`model_dump()` is JSON-ready for the host).
4. `available_providers()` (sorted registry keys) feeds the admin settings dropdown (`GET /api/admin/scoring`) and validates `PUT /api/admin/scoring`.

## Integration

- **Upstream**: imported only by `backend/main.py`; requires `backend/` on `sys.path` (natural when running `main.py`, manual setup for standalone scripts).
- **Input**: WAV recordings (16 kHz / 16-bit / mono) captured directly by the frontend — no transcoding anywhere in the chain.
- **Downstream**: concrete provider implementations in `echoic/providers/` (registry keys `mock`, `unisound`); their keys/options come from `data/scoring.json` (editable via the Admin page, effective immediately).
- **Docs**: provider onboarding rules in `docs/design.md` §7.
