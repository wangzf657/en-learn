# EnLearn 设计文档

## 1. 总体架构

单进程单端口，无前后端分离部署：

```
┌─ 浏览器 http://127.0.0.1:8420 ─────────────────────┐
│  Vue3 SPA（frontend/dist 静态文件）                  │
│  /            日历首页 Home.vue                      │
│  /play/:date  播放页 Play.vue（含跟读录音）           │
│  /admin       后台 Admin.vue                        │
└──────────────┬──────────────────────────────────────┘
               │ /api/*（fetch JSON / multipart）
┌──────────────▼──────────────────────────────────────┐
│  FastAPI 单进程 (backend/main.py, ~290 行)            │
│  ├─ REST API（sqlite3 标准库直连）                    │
│  ├─ 视频流 FileResponse（原生支持 Range → 206）       │
│  ├─ 跟读评分 /api/score（同步 def，线程池执行）        │
│  └─ 其余路径托管 dist 静态文件 + SPA fallback          │
└───────┬──────────────────────┬───────────────────────┘
        │                      │
 data/enlearn.db         backend/echoic/（纯 Python 库）
 （SQLite 单文件）        ASR + 强制对齐 + 音素级评分
                         （无 HTTP 无 DB，模型 ~1GB 首次下载缓存）
```

**关键取舍**：
- **单端口托管前端**：生产免 nginx，dev 用 vite proxy `/api`，同一套前端代码两种环境无差异
- **sqlite3 标准库无 ORM**：表就两张，ORM 纯属负担；每请求短连接（`closing(db())`），单用户量级足够
- **视频不复制入库，只存路径**：视频文件大且已有，流式接口按 id 查路径后 `FileResponse`；文件被移走时播放返回 404，后台有 validate-path 提前验证
- **原生 `<video>` 而非 video.js**：倍速/暂停/进度全是浏览器自带能力，零依赖满足需求
- **评分能力封装为纯库 echoic，宿主只做薄接口**：ASR/对齐/评分是独立的模型链路，与 HTTP/DB 解耦后可独立演进复用；宿主 `main.py` 只加一个上传→调库→返回的端点，不感知模型细节
- **评分不落库**：需求定位是即时反馈而非历史统计，省一张表 + 一套查询；将来要历史只需加 `scores` 表 + 评分返回体原样入库

## 2. 数据模型

```sql
videos  (id, date UNIQUE, title, video_path, subtitle_json, created_at)
checkins(date PRIMARY KEY, video_id, checked_at)
```

- `videos.date` UNIQUE：一天一视频的约束交给数据库
- `checkins.date` 主键：打卡幂等天然由主键 + `INSERT OR IGNORE` 保证
- `subtitle_json` 存规范化后的 JSON 字符串（原文保留，`ensure_ascii=False` 保中文可读）
- 删视频时手动级联删 checkins（无外键，两条 DELETE 一个事务）

## 3. API 契约

| 方法 | 路径 | 说明 | 错误 |
|---|---|---|---|
| GET | `/api/calendar?month=YYYY-MM` | 当月任务列表（date/videoId/title/checked） | 422 格式 |
| GET | `/api/day/{date}` | 播放页数据：videoUrl、checked、subtitle | 404 当天没有学习任务 |
| POST | `/api/day/{date}/checkin` | 打卡，幂等 | 404 无任务 |
| GET | `/api/videos/{id}/stream` | 视频流，支持 Range（拖进度条必需） | 404 视频不存在/文件不存在 |
| GET/POST | `/api/admin/videos` | 列表（含 sentenceCount/checked）/ 新建 | 409 日期重复；422 校验 |
| PUT/DELETE | `/api/admin/videos/{id}` | 更新（字段可选）/ 删除（级联删打卡） | 404 不存在；409/422 |
| POST | `/api/admin/validate-path` | 验证视频文件存在，返回 size | — |
| POST | `/api/score` | 跟读评分：multipart（audio + reference 文本），返回 ScoringResult | 422 缺参考文本；500 评分失败（附原因） |

校验顺序：**先 409（日期冲突）后 422（字幕校验）**——冲突是最先能判定的错误，避免用户改好 JSON 才发现日期撞了。

## 4. 字幕 JSON 契约

```json
{
  "sentences": [
    {
      "start": 1.2,            // 必填，秒，数字
      "end": 4.5,              // 必填，秒，数字
      "en": "How you doing?",  // 必填
      "zh": "你好吗？",          // 可选，中文翻译
      "words": [               // 可选，重点词
        { "w": "doing", "phonetic": "ˈduːɪŋ", "note": "美式常用问候" }
      ],
      "note": "整句笔记"        // 可选
    }
  ]
}
```

服务端 `normalize_subtitle()` 逐句校验 start/end/en 类型，非法 422；words/note 结构前端容错渲染，不强校验（自用数据，宁松勿卡）。

## 5. 跟读评分设计（echoic 集成）

> 状态：**规划中**——`backend/echoic/` 库已就位并经独立验证，宿主端点 `/api/score` 与前端录音 UI 待实现。

### 调用链

```
前端 MediaRecorder 录音(webm/opus)
  → FormData(audio, reference) POST /api/score（同步 def 端点，线程池执行）
    → 存临时文件 → echoic.score_recording(path, reference_text)
      → 对齐(wav2vec2) + 音素级评分 → ScoringResult
    → 删临时文件 → result.model_dump() 返回 JSON
  → 前端渲染三维分数 + 逐词得分
```

### echoic 包（backend/echoic/，已存在的纯库）

```
echoic/__init__.py       # 入口：transcribe / score_recording / phonemize_words，服务实例 lru_cache
echoic/config.py         # EchoicSettings（ECHOIC_ 前缀环境变量，如 ECHOIC_ASR__MODEL_SIZE）
echoic/schemas.py        # Sentence / WordScore / ScoringResult
services/asr/            # faster-whisper 转写 + VAD 分句
services/alignment/      # wav2vec2 强制对齐（英文 torchaudio CTC，其余 whisperx）
services/scoring/        # CTC 强制对齐评分 + 按语言分发音素化后端
```

### 宿主端点约束（main.py 侧必须遵守）

- **同步 `def` 而非 `async def`**：评分 CPU 密集（秒级），async 会卡死事件循环；FastAPI 对 `def` 自动走线程池
- **服务实例已按语言 `lru_cache`**：重复调用无模型重载开销，端点直接调函数即可，无需自己缓存
- **webm 直评**：音频解码在 echoic 内部走 ffmpeg subprocess，宿主只需落盘上传文件
- **对齐失败不报错**：对齐不上的词计 0 分，端点只在整体异常（如空音频）时 4xx/5xx

### 评分结果契约（ScoringResult.model_dump()）

```json
{
  "accuracy_score": 82.5,
  "fluency_score": 78.0,
  "completeness_score": 90.0,
  "word_scores": [
    {
      "word": "doing",
      "accuracy_score": 85.0,
      "expected_phonemes": "ˈduːɪŋ",
      "actual_phonemes": "duːɪŋ",
      "phoneme_scores": [0.9, 0.8, 0.7]
    }
  ]
}
```

前端展示要点：分数已校准（0.25 幂变换，原始 30–60% 映射到 74–88% 展示区间），直接展示即可，**不要**用展示分数再调阈值或二次换算；"词是否说了"的判定阈值在原始尺度上，由 echoic 内部处理。

### 系统依赖与降级

| 依赖 | 缺失时的行为 |
|---|---|
| ffmpeg | 音频解码失败，评分接口报错（需安装） |
| espeak-ng | **英文音素化静默退化**：回退成原词，分数失真但不报错——分数异常先查它 |
| fugashi/jaconv | 日语评分退化但可用（Windows 无 wheel，装不上属预期） |

首次调用评分时三个模型（约 1 GB）从 HuggingFace 下载并永久缓存，首次慢是正常现象。

## 6. 前端设计

```
frontend/src/
├─ api.js            # 全部 fetch 封装（与后端契约逐字对齐）
├─ views/Home.vue    # 日历：当月网格、月份切换、打卡标记、齿轮入口
├─ views/Play.vue    # 播放页核心（下文详述）
├─ views/Admin.vue   # 后台：表格 + 表单弹窗、路径验证、JSON 导入/粘贴
└─ utils/date.js     # 日期工具
```

无 UI 组件库、无日历库、无播放器库——三页面的量级，原生控件 + 自写 CSS 更小更快。

### 双向时间轴绑定（核心交互，Play.vue）

- **video → sentence**：`timeupdate` 事件里二分/线性找 `start ≤ t < end` 的句子，命中则高亮 + `scrollIntoView({block:'nearest'})`
- **sentence → video**：点击句子 `video.currentTime = start` 并 `play()`
- 自动打卡：`ended` 事件或 `timeupdate` 中 `t/duration ≥ 0.9` 触发 checkin，前端只发一次（后端幂等兜底）

### 跟读录音交互（规划中，Play.vue）

- 每句卡片提供"跟读"按钮：点击开始/停止录音，`MediaRecorder` 采集麦克风（webm/opus）
- 停止后自动 `FormData(audio, reference=句子en)` 上传 `/api/score`，期间按钮显示评分中（评分秒级，需防重复提交）
- 结果渲染：句级三分数（准确/流利/完整）+ 逐词着色（好/中/差三档）+ 点词展开 expected/actual 音素对比
- 录音期间暂停视频播放（避免视频声音混入麦克风）；评分失败 toast 提示，不影响页面其他功能

### Dev/Prod 一致性

- dev：`vite.config.js` proxy `/api` → `127.0.0.1:8420`；`MOCK=1` 时 `mockApiPlugin.js` 在 dev server 内拦截 `/api` 返回假数据，可纯前端独立开发
- prod：`npm run build` 产出 dist，后端 SPA fallback（非 `/api` 未知路径回落 index.html，且防目录穿越）

## 7. 验证体系

- `backend/smoke_test.py`：自包含冒烟（起真实服务 → 20 断言 → finally 清理临时 db/mp4）：CRUD、409/422、Range 206+Content-Range、打卡幂等、SPA 托管、fallback、级联删除
- `frontend/src/tests/*.spec.js`（vitest + happy-dom）4 例：日历渲染、句子高亮、点击 seek、后台表单校验
- `frontend/smoke-dev.mjs`：dev server + MOCK 冒烟
- 评分链路（实现后补）：smoke 增加 `/api/score` 422 分支（缺 reference）+ 一次真实评分断言（需模型缓存就绪，耗时长可单独开关跳过）；前端补录音组件交互测试（mock `/api/score`）

## 8. 已知边界

- 并发写 SQLite 靠短事务 + WAL 默认配置，单用户无风险；多用户需重估（非目标）
- 视频路径为绝对路径存库，文件挪走即 404（有 validate-path 缓解）
- `vue-router@5` / `vite@8` 均为当前 major，锁版本在 package.json caret 范围内
- 评分接口为 CPU 密集同步调用（秒级），单用户场景下并发跟读评分不会出现；若将来多人使用需考虑队列/进程池隔离
- echoic 的系统依赖与降级行为见 §5 表格——尤其 espeak-ng 缺失导致的英文评分静默失真，排查分数异常时优先检查
- 首次评分触发 ~1 GB 模型下载，离线环境不可用（模型缓存后无网可用）
