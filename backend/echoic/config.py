from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class WhisperXConfig(BaseModel):
    model_size: str = "base"        # tiny / base / small / medium / large-v2
    device: str = "cpu"             # cpu / cuda (CTranslate2: no MPS support)
    compute_type: str = "int8"      # int8 / float16 / float32
    language: str = "en"
    batch_size: int = 16


class Wav2Vec2AlignmentConfig(BaseModel):
    model_id: str = "facebook/wav2vec2-base-960h"
    device: str = "cpu"             # cpu / cuda / mps
    language: str = "en"


class PhonemeScoringConfig(BaseModel):
    phoneme_model_id: str = "facebook/wav2vec2-lv-60-espeak-cv-ft"
    device: str = "cpu"             # cpu / cuda / mps
    language: str = "en-us"         # espeak language code
    accuracy_weight: float = 0.5
    fluency_weight: float = 0.3
    completeness_weight: float = 0.2


class EchoicSettings(BaseSettings):
    """Echoic configuration. Zero-config defaults; override via env vars with
    the ECHOIC_ prefix and __ nesting, e.g. ECHOIC_ASR__DEVICE=cuda."""

    model_config = SettingsConfigDict(env_prefix="ECHOIC_", env_nested_delimiter="__")

    asr: WhisperXConfig = WhisperXConfig()
    alignment: Wav2Vec2AlignmentConfig = Wav2Vec2AlignmentConfig()
    scoring: PhonemeScoringConfig = PhonemeScoringConfig()


settings = EchoicSettings()
