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
│  FastAPI 单进程 (backend/main.py, ~350 行)            │
│  ├─ REST API（sqlite3 标准库直连）                    │
│  ├─ 视频流 FileResponse（原生支持 Range → 206）       │
│  ├─ 跟读评分 /api/score（同步 def，线程池执行）        │
│  └─ 其余路径托管 dist 静态文件 + SPA fallback          │
└───────┬──────────────────────┬───────────────────────┘
        │                      │
  data/enlearn.db         backend/echoic/（云 API 对接壳）
  （SQLite 单文件）        统一入口 + 多 provider 注册表（mock + unisound）
```

**关键取舍**：
- **单端口托管前端**：生产免 nginx，dev 用 vite proxy `/api`，同一套前端代码两种环境无差异
- **sqlite3 标准库无 ORM**：表就两张，ORM 纯属负担；每请求短连接（`closing(db())`），单用户量级足够
- **视频不复制入库，只存路径**：视频文件大且已有，流式接口按 id 查路径后 `FileResponse`；文件被移走时播放返回 404（按月导入时路径即来自磁盘扫描，重新导入同目录即可修复）
- **原生 `<video>` 而非 video.js**：倍速/暂停/进度全是浏览器自带能力，零依赖满足需求
- **录入只走按月导入，重复导入即覆盖**：实际工作流是按月整理 `01_标题.mp4` 文件夹一次导入；覆盖语义（同日期 UPDATE，id 与打卡保留）让"重导修复"零心智负担，因此不需要单条增改表单
- **评分走云 API，echoic 只做对接壳**：统一入口 `score_recording()` + provider 注册表，后台配置切厂商（单机自用量级月成本个位数，选型见 docs/scoring-api-research.md）；宿主 `main.py` 只加一个上传→调库→返回的端点，不感知厂商细节
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
| GET | `/api/admin/videos` | 列表（含 sentenceCount/checked） | — |
| DELETE | `/api/admin/videos/{id}` | 删除（级联删打卡） | 404 不存在 |
| POST | `/api/admin/videos/import` | 按月批量导入 `{path, month}`：解析 `01_标题.mp4` 命名，同日期覆盖（id/打卡保留），同名 .json 自动作字幕；返回 `{imported[]（含 updated）, skipped[]（含原因）}` | 422 month 格式 / 文件夹不存在 |
| POST | `/api/score` | 跟读评分：multipart（audio + reference 文本），返回 ScoringResult | 422 缺字段；500 评分失败（附原因） |
| GET/PUT | `/api/admin/scoring` | 读写评分 provider 配置（`data/scoring.json`，原子写，请求时现读即时生效）；GET 附 `providers` 下拉 | 422 未知 provider |

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

## 5. 跟读评分设计（云 API，echoic 对接壳）

> 状态：**已实现并经真实 API 验收**——宿主端点 `/api/score`、前端录音评分 UI、云知声 unisound provider 均已上线（2026-09 用真实密钥走通完整链路）。本地模型栈已于 2026-09 整体移除（决策记录：docs/scoring-api-research.md）。

### 调用链

```
前端录 WAV(16k/16bit/单声道，AudioContext 采集，前端封 WAV 头)
  → FormData(audio, reference) POST /api/score（同步 def 端点，线程池执行）
    → 读 data/scoring.json（provider + options）
    → 存临时文件 → echoic.score_recording(path, reference_text, provider, options)
      → provider 调云 API → 统一 ScoringResult
    → 删临时文件 → result.model_dump() 返回 JSON
  → 前端渲染三维分数 + 逐词得分
```

### echoic 包（backend/echoic/，对接壳）

```
echoic/__init__.py       # 入口：score_recording()，按 provider 名分发
echoic/schemas.py        # WordScore / ScoringResult（0–100）
echoic/providers/base.py # ScoringProvider 协议 + 注册表（register/get/available）
echoic/providers/mock.py # 固定分数假 provider（联调/冒烟）
echoic/providers/unisound.py # 云知声口语评测（线上 provider）
```

新增厂商：`ScoringProvider` 子类（类属性 `name` 为注册表键）→ `providers/__init__.py` 登记一行 → 后台配置切换。架构详见 docs/scoring-provider-design.md，厂商对比与价格见 docs/scoring-api-research.md。

### 宿主端点约束（main.py 侧必须遵守）

- **同步 `def` 而非 `async def`**：评分是云 API 网络调用（百毫秒~秒级），FastAPI 对 `def` 自动走线程池
- **provider 配置从 `data/scoring.json` 读**：`{ "provider": "unisound", "options": {...} }`，每次请求读（文件小、单用户），改配置即时生效无需重启；Admin 页表单读写（GET/PUT `/api/admin/scoring`，原子写）
- **厂商异常映射**：provider 抛带原因异常 → 端点 500 附原因；参考词没念出来是低分不是错误
- **零系统依赖**：音频格式在前端就收敛为 WAV，后端落盘即传，无 ffmpeg/espeak-ng

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
      "phoneme_scores": [90.0, 80.0, 70.0]
    }
  ]
}
```

分数是**厂商原始校准分**，直接展示，不做二次换算（旧本地栈的 0.25 幂校准已随栈废弃）；不同厂商分数分布不同，换 provider 后分数不可比。

## 6. 前端设计

```
frontend/src/
├─ api.js            # 全部 fetch 封装（与后端契约逐字对齐）
├─ views/Home.vue    # 日历：当月网格、月份切换、打卡标记、齿轮入口
├─ views/Play.vue    # 播放页核心（下文详述，含跟读录音评分）
├─ views/Admin.vue   # 后台：视频列表 + 按月快捷导入、评分服务配置
├─ utils/recorder.js # 录音：AudioContext 采 16k PCM + 前端封 WAV 头
└─ utils/date.js     # 日期工具
```

无 UI 组件库、无日历库、无播放器库——三页面的量级，原生控件 + 自写 CSS 更小更快。

### 双向时间轴绑定（核心交互，Play.vue）

- **video → sentence**：`timeupdate` 事件里二分/线性找 `start ≤ t < end` 的句子，命中则高亮 + `scrollIntoView({block:'nearest'})`
- **sentence → video**：点击句子 `video.currentTime = start` 并 `play()`
- 自动打卡：`ended` 事件或 `timeupdate` 中 `t/duration ≥ 0.9` 触发 checkin，前端只发一次（后端幂等兜底）

### 跟读录音交互（已实现，Play.vue + utils/recorder.js）

- 每句卡片提供"跟读"按钮：点击开始/停止录音；**直接录 WAV（16k/16bit/单声道）**——`AudioContext({sampleRate:16000})` 采 PCM、前端封 WAV 头（所有候选云 API 都不收 webm，别用 MediaRecorder 默认格式）
- 停止后自动 `FormData(audio, reference=句子en)` 上传 `/api/score`，期间按钮显示评分中（评分秒级，需防重复提交）
- 结果渲染：句级三分数（准确/流利/完整）+ 逐词着色（好/中/差三档）+ 点词展开 expected/actual 音素对比
- 录音期间暂停视频播放（避免视频声音混入麦克风）；评分失败 toast 提示，不影响页面其他功能

### Dev/Prod 一致性

- dev：`vite.config.js` proxy `/api` → `127.0.0.1:8420`；`MOCK=1` 时 `mockApiPlugin.js` 在 dev server 内拦截 `/api` 返回假数据，可纯前端独立开发
- prod：`npm run build` 产出 dist，后端 SPA fallback（非 `/api` 未知路径回落 index.html，且防目录穿越）

## 7. 验证体系

- `backend/smoke_test.py`：自包含冒烟（起真实服务 → 32 断言 → finally 清理临时 db/导入目录，scoring.json 快照还原）：CRUD、422、Range 206+Content-Range、打卡幂等、SPA 托管与 fallback、级联删除、按月导入（新增/覆盖/跳过/422）、评分链路（mock provider）、scoring 配置读写
- `frontend/src/tests/*.spec.js`（vitest + happy-dom）4 文件 9 例：日历渲染、句子高亮、点击 seek、跟读评分结果、录音 WAV 封装、按月导入（含覆盖标签）
- `frontend/smoke-dev.mjs`：dev server + MOCK 冒烟（mock 含 /api/score、scoring 配置、按月导入）
- echoic：`providers/unisound_test.py` 离线自测（真实 API 需密钥，已单独用真实密钥人工验收）

## 8. 已知边界

- 并发写 SQLite 靠短事务 + WAL 默认配置，单用户无风险；多用户需重估（非目标）
- 视频路径为绝对路径存库，文件挪走即 404（按月导入按文件夹录入，文件挪动后重导同目录即可修复）
- `vue-router@5` / `vite@8` 均为当前 major，锁版本在 package.json caret 范围内
- 评分走云 API：需外网，断网时跟读评分不可用（其余功能不受影响，mock provider 可兜底联调）
- 各厂商分数分布不同，换 provider 后观感会变——首版评分不落库，影响仅当次会话
