"""Echoic — pronunciation scoring capability.

Pure library: ASR (faster-whisper) + forced alignment (wav2vec2) +
phoneme-level scoring (wav2vec2 CTC). No HTTP, no database.

Typical usage from the host app (backend/ is on sys.path when running
backend/main.py, so `import echoic` works directly):

    from echoic import transcribe, score_recording

    sentences = transcribe("lesson.mp3")
    result = score_recording("attempt.webm", reference_text="Hello world")
    payload = result.model_dump()   # JSON-ready

ML models download on first use (~1 GB total) and cache in the HuggingFace
cache dir. All calls are synchronous and CPU-bound: call them from `def`
FastAPI endpoints (threadpool), not `async def`.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

from .config import settings

if TYPE_CHECKING:
    from .schemas import Sentence
    from .services.scoring.base import ScoringResult


@lru_cache(maxsize=None)
def _asr_service(language: str | None = None):
    from .services.asr.whisperx import WhisperXASRService

    if language is None or language == settings.asr.language:
        return WhisperXASRService(settings.asr)
    return WhisperXASRService(settings.asr.model_copy(update={"language": language}))


@lru_cache(maxsize=None)
def _alignment_service(language: str | None = None):
    from .services.alignment.wav2vec2 import Wav2Vec2AlignmentService

    if language is None or language == settings.alignment.language:
        return Wav2Vec2AlignmentService(settings.alignment)
    return Wav2Vec2AlignmentService(
        settings.alignment.model_copy(update={"language": language})
    )


@lru_cache
def _scoring_service():
    from .services.scoring.phoneme import PhonemeScoringService

    return PhonemeScoringService(settings.scoring)


def transcribe(audio_path: str, language: str | None = None) -> "list[Sentence]":
    """Transcribe an audio file into sentences with word-level timestamps."""
    return _asr_service(language).transcribe(audio_path)


def score_recording(
    recording_path: str,
    reference_text: str,
    language: str | None = None,
) -> "ScoringResult":
    """Score a user recording against a reference sentence.

    Returns ScoringResult(accuracy_score, fluency_score, completeness_score,
    word_scores). Words the user skipped or badly mispronounced get 0.
    """
    aligned_words = _alignment_service(language).align(recording_path, reference_text)
    return _scoring_service().score(
        recording_path, reference_text, aligned_words, language=language
    )


def phonemize_words(words: list[str], language: str | None = None) -> list[str]:
    """Return display phonemes per word (IPA; romaji for Japanese)."""
    if language is None:
        return _scoring_service().phonemize_words(words)
    from .services.scoring.backends import get_backend

    return get_backend(language).display(words)


__all__ = ["transcribe", "score_recording", "phonemize_words", "settings"]
