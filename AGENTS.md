# AGENTS.md

面向 AI 编码代理的仓库指南。

## 项目结构

`en-learn` — 英语学习应用,单仓三部分:

- `backend/main.py` — 宿主后端,单文件 FastAPI + SQLite(`data/enlearn.db`),视频/字幕/打卡管理,`start.bat` 一键启动(端口 8420)
- `backend/echoic/` — **发音评分能力封装**:纯 Python 库,无 HTTP、无数据库,只做 ASR + 强制对齐 + 音素级评分
- `frontend/` — 前端,构建产物 `frontend/dist/` 由宿主后端托管(未构建时返回提示)

工作环境:上层共享 `.venv`(Python 3.10),依赖见 `backend/requirements.txt`,`start.bat` 首次运行自动安装。**无 lint/CI/格式化工具**,唯一验证手段是 `backend/smoke_test.py`(`.venv\Scripts\python.exe backend\smoke_test.py`)。

## echoic 评分包

### 入口(供上传/评分流程调用)

```python
from echoic import transcribe, score_recording, phonemize_words

# 1. 转写音频 → 句子列表(含词级时间戳),用于切分跟读素材
sentences = transcribe("lesson.mp3")            # [Sentence(index, text, start, end, words)]

# 2. 评分:用户录音 vs 参考文本(上传流程的核心调用)
result = score_recording("attempt.webm", reference_text="Hello world")
result.model_dump()  # JSON-ready: accuracy/fluency/completeness_score + word_scores

# 3. 音素显示(IPA,日语返回罗马音)
phonemize_words(["hello", "world"])
```

调用约束:
- **同步 CPU 密集**,在 FastAPI 端点里必须用 `def`(线程池),不要 `async def`(阻塞事件循环)
- 服务实例按语言 `lru_cache` 缓存,重复调用无额外模型加载开销
- 每个函数都接受可选 `language` 参数(如 `"ja"`/`"fr"`),默认走配置语言

### 配置

零配置可用,全部默认值。覆盖用环境变量,前缀 `ECHOIC_` + `__` 嵌套:

```env
ECHOIC_ASR__MODEL_SIZE=base      # tiny/base/small/medium/large-v2
ECHOIC_ASR__DEVICE=cpu           # CTranslate2 不支持 MPS
ECHOIC_ALIGNMENT__DEVICE=cpu     # wav2vec2 支持 cpu/cuda/mps
ECHOIC_SCORING__LANGUAGE=en-us   # espeak 语言码: en-us / fr-fr / de / ja
```

### 包内结构

```
echoic/__init__.py            # 三个入口函数 + 缓存的服务构建器
echoic/config.py              # EchoicSettings (ECHOIC_ 前缀)
echoic/schemas.py             # Sentence / WordTimestamp / WordScore / ScoringResult
echoic/services/asr/          # faster-whisper 转写,VAD 分句合并
echoic/services/alignment/    # wav2vec2 强制对齐(英文走 torchaudio CTC,其余走 whisperx)
echoic/services/scoring/      # CTC 强制对齐评分 + 按语言分发的音素化后端
```

## 关键坑

- **首次调用慢是正常的**:三个模型(~1 GB)首次使用时从 HuggingFace 下载并永久缓存,不是卡死。
- **系统依赖**:ffmpeg(音频解码走 subprocess)+ espeak-ng(音素化)。**espeak-ng 缺失时英文评分会静默退化**(音素化回退成原词,分数失真),不报错——装了但分数异常先查这个。
- 日语音素链路需要 fugashi/jaconv,Windows 无 wheel 装不上;缺失时日语评分退化但可用。
- 分数经过校准(0.25 幂变换,原始 30–60% 映射到 74–88% 展示区间);词"是否说了"的判定阈值在原始尺度上,不要拿展示分数调阈值。
- `score_recording` 内部先对齐再评分,对齐失败的词计 0 分,不是报错。
