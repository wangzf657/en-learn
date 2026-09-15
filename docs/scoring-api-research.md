# 发音评分云 API 选型调研

> 调研时间:2026-09,数据以当时官方页面为准;标注"估算"的项未经一手来源核实。
> 背景:单用户自用,每月 ≤1000 次跟读评分,每次音频几秒。
> 决策:放弃本地模型栈,评分走云 API(架构见 docs/scoring-provider-design.md)。
> 最终选型:**云知声口语评测**(sacalleval HTTP API)——调研后期补充验证后采用:REST 直连、鉴权简单、逐词逐音素齐全、按次计费;下表为当时对比快照,未含云知声。

## 对比总表

| API | 免费额度 | 付费价格 | 音素级 | 输入格式 | 国内直连 |
|---|---|---|---|---|---|
| **腾讯云智聆口语评测(新版)** | 无免费月度额度 | 后付费 0.005 元/次;套餐 1 万次 ¥9.9(限时)、15 万次 ¥600 | ✅ GOP + IPA + 重音检测 | pcm/wav/mp3/speex,16k/16bit/单声道;**不收 webm/ogg** | ✅ |
| 讯飞 suntone(新一代) | 中英文 1000 次/30 天 | 中英文 1 万次 ¥50、20 万次 ¥900、100 万次 ¥4000;小语种约翻倍 | ✅ `words.phonemes[]` | WebSocket 流式,16k 为主 | ✅ |
| 讯飞 ISE(旧版) | 新用户 1 万次/90 天(个人认证) | 20 万次 ¥1200/年 | ✅ 音节/音素 | WebSocket 流式 | ✅ |
| Azure AI Speech 发音评估 | F0:5 音频小时/月(PA 按标准 STT 计费,推断覆盖,官方未单列) | 实时 ~$1.0–1.3/时(两来源冲突,估算);短音频 REST $0.66/时;prosody 加购 $0.30/时;azure.cn:STT ¥3/时 + PA 加购 ¥3.05/时/功能 | ✅ + 韵律分 | REST 短音频仅 WAV-PCM / OGG-Opus(16k mono);**不收 webm** | 全球版需 VPN;azure.cn 可用(需 21Vianet 实名) |
| ELSA API | 无(B2B 申请制) | Scripted $0.008/15s、Unscripted $0.02/15s | ✅ | 未核实(估算) | 需 VPN |
| Speechmatics | $100 新户额度 | STT $0.129/时起 | 发音测评能力未确认 | — | 需 VPN |
| OpenAI | — | — | ❌ 无此能力(Whisper 仅转写) | — | — |

## 要点

- **月成本**:本用量级三家国内可选 API 都趋近于零——腾讯 ~5 元/月(或 9.9 元 1 万次用一年)、讯飞 suntone ~4 元/月、Azure F0 免费额度大概率够。
- **webm 全军覆没**:浏览器 `MediaRecorder` 默认产 webm/opus,以上 API 均不收。**前端录音直接录 16k/16bit/单声道 WAV**,绕开所有转码,后端也就不需要 ffmpeg。
- **首选候选:腾讯智聆新版**——国内直连、中文文档、Python SDK、价格最低、音素/IPA/重音齐全、支持按次后付费。注意用**新版接口**(基础版即将下线)。
- **备选:Azure**——发音评估质量口碑最好、独有韵律分;但全球版要 VPN,azure.cn 要实名。讯飞 suntone 次选(WebSocket 流式,集成比 REST 重)。
- 无法核实项:Azure 实时价绝对值(官方定价页 JS 渲染)、讯飞/腾讯对 mp3 的明确支持列表、ELSA 音频格式。

## 来源

- 腾讯:cloud.tencent.com/document/product/884/44468(计费)、/1774/107497(新版接口)、/product/soe-overview
- 讯飞:xfyun.cn/services/suntone_ise2025、suntone API 文档(apifox)、xfyun.cn/services/ise
- Azure:azure.microsoft.com/pricing/details/speech、learn.microsoft.com(REST 短音频 / Pronunciation Assessment 文档)、azure.cn/pricing/details/cognitive-services
- ELSA:elsaspeak.com/en/elsa-api;Speechmatics:speechmatics.com/pricing
