from pydantic import BaseModel


class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float


class Sentence(BaseModel):
    index: int
    text: str
    start: float
    end: float
    words: list[WordTimestamp]


class WordScore(BaseModel):
    word: str
    accuracy_score: float
    expected_phonemes: str
    actual_phonemes: str
    phoneme_scores: list[float] = []  # per-phoneme score (stress markers excluded)
