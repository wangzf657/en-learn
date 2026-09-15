"""echoic 数据契约(0–100 分制,全链路统一)。"""

from pydantic import BaseModel


class WordScore(BaseModel):
    word: str
    accuracy_score: float       # 0–100
    expected_phonemes: str      # 展示用音素串(IPA 或厂商记法)
    actual_phonemes: str
    phoneme_scores: list[float] = []  # 逐音素分,0–100


class ScoringResult(BaseModel):
    accuracy_score: float       # 0–100,发音准确度
    fluency_score: float        # 0–100,流利度
    completeness_score: float   # 0–100,完整度(说了多少参考词)
    word_scores: list[WordScore]
