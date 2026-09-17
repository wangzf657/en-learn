"""echoic 数据契约(0–100 分制,全链路统一)。

除三维总分与逐词分,还透出云厂商能提供的「诊断」信息:
ASR 识别对比(sample/usertext)、词类型(漏词/错词/多词)、重音、音质检测——
供前端在不失真的前提下展示更专业的反馈。
"""

from pydantic import BaseModel


class AudioQuality(BaseModel):
    """录音音质检测(云知声 audiocheck 归一)。字段为 True 表示检测到该问题。"""

    volume: bool = False        # 音量过小
    clipping: bool = False      # 削波/破音
    noise: bool = False         # 噪声
    cut: bool = False           # 截断(录音不完整)
    too_short: bool = False     # 过短
    empty_audio: bool = False   # 空音频


class WordScore(BaseModel):
    word: str
    accuracy_score: float       # 0–100
    expected_phonemes: str      # 展示用音素串(IPA 或厂商记法)
    actual_phonemes: str
    phoneme_scores: list[float] = []  # 逐音素分,0–100
    phonemes: list[str] = []          # 逐实际音素(与 phoneme_scores 对齐,前端着色用)
    type: int = 2                     # 词类型:0多词 1漏词 2正常 3错词(静音/重复/标点已滤除)
    stress: int = -1                  # 重音:-1未知 0错 1对


class ScoringResult(BaseModel):
    accuracy_score: float       # 0–100,发音准确度
    fluency_score: float        # 0–100,流利度
    completeness_score: float   # 0–100,完整度(说了多少参考词)
    word_scores: list[WordScore]
    sample: str = ""            # 参考/标准文本
    usertext: str = ""          # ASR 识别结果(学习者实际念出来的)
    audio_quality: AudioQuality | None = None