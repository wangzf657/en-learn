# 多 Provider 评分架构设计

> 决策:放弃本地模型栈(faster-whisper/wav2vec2/torch 全家桶已于 2026-09 整体移除),
> 评分走云 API。选型数据与厂商对比见 docs/scoring-api-research.md。
> echoic 保留为纯对接壳:统一入口 + 多 provider 实现 + 后台配置切换。

## 结构(已实现)

```
echoic/
├─ __init__.py        # 统一入口 score_recording()
├─ schemas.py         # ScoringResult / WordScore(0–100,全链路统一)
└─ providers/
    ├─ base.py        # ScoringProvider 协议 + 注册表(register/get/available)
    ├─ mock.py        # 固定分数假 provider(前端联调/冒烟测试)
    └─ unisound.py    # 云知声口语评测(线上 provider;sacalleval HTTP API)
```

## 核心约定

- **统一入口**:`echoic.score_recording(recording_path, reference_text, provider=, options=, language=)` → `ScoringResult`,`model_dump()` 即 JSON-ready
- **依赖注入**:provider 名与 options(密钥/区域等)由宿主从后台配置读出后传入;echoic 不读配置文件、不碰环境变量、无全局状态——纯函数式分发
- **协议**:每家 API 一个 `ScoringProvider` 子类,类属性 `name` 是注册表键(后台配置引用它);`score()` 里网络/认证/参数错误抛带可读原因的异常(宿主映射 5xx),参考词没念出来计低分不报错
- **注册**:实现完在 `providers/__init__.py` 登记一行;`available_providers()` 供后台配置页做下拉
- **分数**:厂商原始校准分直接进 `ScoringResult`,**不做任何二次变换**(旧本地栈的 0.25 幂校准已随栈废弃);不同厂商分数分布不同,换 provider 不追求分数可比

## 音频格式(硬约束)

调研确认所有候选 API 都不收 webm。**前端录音直接录 WAV(16k/16bit/单声道)**:
`new AudioContext({sampleRate: 16000})` + ScriptProcessor/AudioWorklet 采 PCM,
前端封 WAV 头后上传。后端零转码,不依赖 ffmpeg(旧栈的 ffmpeg/espeak-ng 依赖全部移除)。

## 宿主接入(已实现)

- `/api/score`:multipart(audio + reference),同步 `def` 端点(线程池),
  落盘临时文件 → `score_recording()` → 删临时文件 → `model_dump()` 返回
- 后台配置用 `data/scoring.json`(provider 名 + options;单机自用,明文即可):
  ```json
  { "provider": "unisound", "options": { "appkey": "...", "secret": "..." } }
  ```
  Admin 页"发音评分服务"表单(下拉选 provider + 填密钥)读写该文件
  (GET/PUT `/api/admin/scoring`,原子写;后端每次请求现读,改配置即时生效)
- **unisound provider 要点**(`providers/unisound.py`,离线自测 `unisound_test.py`):
  - `POST http://edu.hivoice.cn/eval/pcm`,header `appkey: AppKey@AppSecret` + `session-id`(uuid),
    multipart 字段顺序必须 `text → mode → voice`(云知声要求)
  - mode 默认 E(句子跟读);词级/音素分 0–10 制 → ×10 归一到 0–100;行级分为百分制原样保留
  - 厂商错误码映射为带中文原因的异常;多行参考文本行分取均值
- 换厂商参考:腾讯 `tencentcloud-sdk-python-soe` 新版接口 → `providers/tencent.py`,
  依赖加进 backend/requirements.txt,`providers/__init__.py` 登记一行
- 评分仍不落库(见 docs/requirements.md 非目标)
