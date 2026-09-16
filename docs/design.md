# EnLearn 设计文档

## 1. 总体架构

单进程单端口，无前后端分离部署：

```
┌─ 浏览器 http://127.0.0.1:8420 ─────────────────────┐
│  Vue3 SPA（frontend/dist 静态文件）                  │
│  /            日历首页 Home.vue                      │
│  /play/:date  播放页 Play.vue（含跟读录音）           │
│  /local       自由播放 LocalPlay.vue（本地文件夹）    │
│  /admin       后台 Admin.vue                        │
└──────────────┬──────────────────────────────────────┘
               │ /api/*（fetch JSON / multipart）
┌──────────────▼──────────────────────────────────────┐
│  FastAPI 单进程 (backend/main.py, ~350 行)            │
│  ├─ REST API（sqlite3 标准库直连）                    │
│  ├─ 视频流 FileResponse（原生支持 Range → 206）       │
│  ├─ 跟读评分 /api/score（同步 def，线程池执行）        │
│  └─ 其余路径托管 dist 静态文件 + SPA fallback          │
└───────┬──────────────────────┬──────────────┬────────┘
        │                      │              │
  data/enlearn.db      data/library.json   backend/echoic/（云 API 对接壳）
  （SQLite 单文件）     （统一前缀 root）    统一入口 + 多 provider 注册表（mock + unisound）
```

**关键取舍**：
- **单端口托管前端**：生产免 nginx，dev 用 vite proxy `/api`，同一套前端代码两种环境无差异
- **sqlite3 标准库无 ORM**：表就四张，ORM 纯属负担；每请求短连接（`closing(db())`），单用户量级足够
- **课程 → 素材两级**：`courses` = 统一前缀下被导入的文件夹（一季/一套，如 wowEnglish 第一季 = 1 课程 33 素材），`materials` = 课程内的 mp4 + 同名 `.json` 字幕。导入/删除以课程为单位，素材是排期与已读的最小单位
- **排期职责归打卡管理**：`day_materials` 只管"哪天学哪些素材"，与课程内容解耦；同一素材可排多天，删课程/素材只删对应排期行，并清理因此变空的天（连打卡一起删）
- **只存相对路径 + 统一前缀**：`courses.rel_path` / `materials.rel_path` 相对 `data/library.json` 的 root（绝对路径），整个素材库挪盘只改 root 一处；文件被移走时播放 404，重导同目录即可修复并保持 id（库内挪动位置 = rel_path 变了 = 新素材）
- **原生 `<video>` 而非 video.js**：倍速/暂停/进度全是浏览器自带能力，零依赖满足需求
- **录入只走课程导入，同一文件重导即覆盖**：选统一前缀内的文件夹，一次导入整门课程（不递归，只取直接子级 `*.mp4`，按文件名自然排序：数字段按数值，`10.omega` 排在 `4.delta` 后）；幂等键是 `rel_path`——重导 UPDATE 标题与字幕（id 稳定），文件夹里消失的文件保留不删；坏字幕进 skipped 且不占素材位，因此不需要单条增改表单
- **排课按天均分，素材不够就留空**：打卡管理里选课程 + 日期区间（可跨月），素材自然排序后均分给各天（5 素材 / 4 天 → 2-1-1-1）；素材数 < 天数时前 n 天各 1、后面留空（不报错，之后可逐天补）
- **素材已读状态机**：`materials.read_at` 一个可空时间戳，两个入口共用——手动 `PUT /api/admin/materials/{id}/read`，与当天首次打卡自动置位（只填 NULL，手动已读的保留原时间）
- **前缀外不导入**：`folder` 可为绝对路径或相对 root 的子路径，解析后必须落在 root 之下 `rel_path` 才成立；root 未配置时导入与流式接口一律 422
- **评分走云 API，echoic 只做对接壳**：统一入口 `score_recording()` + provider 注册表，后台配置切厂商（单机自用量级月成本个位数，选型见 docs/scoring-api-research.md）；宿主 `main.py` 只加一个上传→调库→返回的端点，不感知厂商细节
- **评分不落库**：需求定位是即时反馈而非历史统计，省一张表 + 一套查询；将来要历史只需加 `scores` 表 + 评分返回体原样入库

## 2. 数据模型

```sql
courses  (id, name, rel_path UNIQUE, created_at)                 -- 课程 = 被导入的文件夹
materials(id, course_id → courses.id ON DELETE CASCADE, title,
          rel_path UNIQUE, subtitle_json, read_at NULL, created_at)
day_materials(date, material_id, PRIMARY KEY(date, material_id)) -- 排期:哪天学哪些素材
checkins (date PRIMARY KEY, checked_at)
```

`data/library.json`：`{ "root": "绝对路径" }`——统一前缀，缺失/损坏时回落空串（等同未配置）。

- `courses.rel_path` / `materials.rel_path` 相对 root 存库（统一 `/` 分隔，如 `wowEnglish-S1/1.视频.mp4`），`materials.rel_path` 的 UNIQUE 即导入幂等键；挪整个素材库只改 root
- 课程与素材是父子：删课程级联删其素材（schema 写了 `REFERENCES ... ON DELETE CASCADE` 表意，实现里手动删，保持行为可见）；文件夹里消失的文件不自动删，保留在库
- `day_materials(date, material_id)` 复合主键：同一素材可排进多个日期，同一日期可排多个素材；`INSERT OR IGNORE` 天然幂等、可叠加
- `materials.read_at` 可空时间戳（ISO 本地时间）：NULL = 未读；手动切换与首次打卡共用，打卡只覆盖 NULL
- `checkins.date` 主键：打卡只按天、与素材解耦（换素材/删素材不影响打卡语义），幂等由主键 + `INSERT OR IGNORE` 保证
- `subtitle_json` 存规范化后的 JSON 字符串（原文保留，`ensure_ascii=False` 保中文可读）
- 无外键级联依赖，删除手动维护：删课程/素材删对应 `day_materials`，并清理因此变空的天的 `checkins`；删空天/移除最后一本素材同样连带删当天 `checkins`

## 3. API 契约

| 方法 | 路径 | 说明 | 错误 |
|---|---|---|---|
| GET/PUT | `/api/admin/library` | 通用设置：读写统一前缀（`data/library.json`，原子写，请求时现读即时生效） | 422 统一前缀目录不存在 |
| POST | `/api/admin/courses/import` | 课程管理·导入：folder（绝对或前缀相对）下的直接子级 `*.mp4` 按文件名自然排序入库为课程素材，同名 `.json` 作字幕；幂等键 `rel_path`（重导 UPDATE，id 稳定），消失的文件保留；返回 `{course{id,name,materialCount}, materials[]{id,title,updated}, skipped[]{file,reason}}` | 422 未配置统一前缀/文件夹不存在/在前缀外 |
| GET | `/api/admin/courses` | 课程列表（id/name/materialCount/readCount/dates[]），按 name 排序；dates = 该课程有素材被排的全部日期 | — |
| GET | `/api/admin/courses/{id}` | 课程详情：materials[]（id/title/relPath/sentenceCount/read/readAt/dates[]，按文件名自然排序） | 404 课程不存在 |
| DELETE | `/api/admin/courses/{id}` | 级联删素材 + 全部排期 + 清孤儿天打卡，返回 `{ok, removedMaterials, removedSchedules}` | 404 课程不存在 |
| DELETE | `/api/admin/materials/{id}` | 删素材 + 级联删排期 + 清孤儿天打卡，返回 `{ok, removedSchedules}` | 404 素材不存在 |
| PUT | `/api/admin/materials/{id}/read` | 已读状态：`{read:bool}`→`{id,read,readAt}`；true 时只在 NULL 上置 now（已读保留原时间），false 置 NULL | 404 素材不存在 |
| POST | `/api/admin/schedule` | 打卡管理·排课：`{courseId,dateFrom,dateTo}`（YYYY-MM-DD，可跨月）；素材自然排序按天均分（n≥d 时前 extra 天 base+1），n<d 时前 n 天各 1、后面留空；`INSERT OR IGNORE` 叠加已有；`{added, scheduled[]{date,materialIds[]}}`（只列区间内涉及的天） | 404 课程不存在；422 日期范围无效 |
| GET | `/api/admin/schedule?month=YYYY-MM` | 月度排期：`{days[]{date,checked,materials[]{id,title,courseName}}}`（该月有排期的天，素材自然排序） | 422 格式 |
| POST | `/api/admin/day/{date}/materials` | 逐天补素材：`{materialIds[]}`，`{added}` | 422 materialIds 不能为空/素材不存在: {id} |
| DELETE | `/api/admin/day/{date}` | 清空当天排期 + 删当天打卡，`{ok, removed}` | — |
| DELETE | `/api/admin/day/{date}/materials/{materialId}` | 移除当天一条素材；当天变空则连带删打卡 | 404 当天没有学习任务；422 当天未排此素材 |
| GET | `/api/calendar?month=YYYY-MM` | 当月任务（date/materialId/title/checked/materialCount；materialId/title = 该日自然排序首素材） | 422 格式 |
| GET | `/api/day/{date}` | 播放页数据：`materials[]`（id/title/videoUrl/srtUrl/subtitle，自然排序）+ checked | 404 当天没有学习任务 |
| POST | `/api/day/{date}/checkin` | 打卡，幂等；首次打卡把当天全部素材 `read_at=now`（只填 NULL，手动已读保留原时间） | 404 无排期 |
| GET | `/api/materials/{id}/stream` | 视频流，支持 Range（拖进度条必需）；root + rel_path 解析 | 422 未配置统一前缀；404 素材/文件不存在 |
| GET | `/api/materials/{id}/srt` | 同目录同名 `.srt` 原样文本（text/plain，服务端去 BOM），前端解析内嵌 | 422 未配置前缀；404 素材/字幕文件不存在 |
| POST | `/api/score` | 跟读评分：multipart（audio + reference 文本），返回 ScoringResult | 422 缺字段；500 评分失败（附原因） |
| GET/PUT | `/api/admin/scoring` | 读写评分 provider 配置（`data/scoring.json`，原子写，请求时现读即时生效）；GET 附 `providers` 下拉 | 422 未知 provider |

## 4. 字幕 JSON 契约

结构唯一权威（机器可读，位于 srt-to-json skill 目录）：**.agents/skills/srt-to-json/subtitle.schema.json**——顶层 `sentences[]`，每句必填 `start/end/en`，可选 `zh/words/note`。生产流程与质量要求见 .agents/skills/srt-to-json/SKILL.md。（原 docs/subtitle-contract.md 已于 2026-09 拆分并入 schema 与本文。）

三类消费方：后端 `normalize_subtitle()` 导入校验入库；前端 Play.vue / SubtitlePanel.vue 渲染句子卡片、时间轴高亮、点击 seek、跟读；`/api/score` 以 `sentence.en` 整句作跟读参考文本——`en` 逐字不得改写。

校验分层（宁松勿卡，自用数据）：
- **硬校验**（服务端 `normalize_subtitle()`）：JSON 合法、顶层含 `sentences` 数组、每句 `start`/`end` 数字且 `en` 字符串。违反 → 导入 422，整条素材跳过（原因"字幕 JSON 无效"）
- **强约定**（生产方，srt-to-json skill 的 check）：`end > start`、时间单调不重叠、`en` 非空无标签残留、`words.w` 能在 `en` 中找到、`phonetic` 不含 `/`、文本守恒。违反 → 拒绝产出，不落库
- **容错渲染**（前端）：`words` 缺失或形状不对不渲染、`zh`/`note` 空则隐藏、未知字段忽略。静默降级
- 服务端有意不校验 `end > start` 与 `zh`/`words` 结构——存量数据不因收紧失效

存储与传输：`materials.subtitle_json` TEXT 存规范化 JSON（`ensure_ascii=False`，中文可读）；`GET /api/day/{date}` 原样透传不二次加工；课程导入读同名 `.json`（必须 UTF-8 无 BOM，BOM 即解析失败整条素材跳过），缺失置空 `{"sentences":[]}`；同目录 `.srt` 与契约无关，仅供 `GET /api/materials/{id}/srt` 下载。

时间轴语义（前端）：高亮按 `start ≤ t < end` 命中，句间空隙不高亮，播过末句后末句保持高亮——句区间应覆盖全部有效教学内容，重叠/错位直接表现为高亮跳变。

演进规则：只增可选字段（旧数据不迁移即兼容）；不改名、不改语义（要改就新增字段、废弃旧字段，前端两代同读）；单机自用不引入 `version` 字段。改结构先改 schema，再改代码。

已知边界：句级 `note` 前端尚未渲染（要么补 UI，要么生产方少写）；服务端不校验 `end > start`（靠生产方自觉）；`sentences` 顺序即渲染顺序，生产方按 `start` 升序产出。

从纯英文 SRT 生成教学 JSON 的离线流水线（结构层本地规则、1 cue = 1 句逐条对齐 + 语义层 agent 富化 + 交付验收，后端零改动）见 **.agents/skills/srt-to-json/SKILL.md**。

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
├─ views/Home.vue    # 日历：当月网格、月份切换、打卡标记
├─ views/Play.vue    # 播放页核心（下文详述，含跟读录音评分、多素材切换）
├─ views/LocalPlay.vue # /local 自由播放：选本地文件夹点播任一 mp4
├─ views/Admin.vue   # 后台：课程管理 + 打卡管理 + 通用设置（统一前缀/评分服务）
├─ components/SubtitleOverlay.vue     # 视频底部内嵌字幕（自绘 overlay，timeupdate 匹配）
├─ components/SubtitleStylePicker.vue # 字幕预设样式切换（清晰/影院/黑底/关闭）
├─ components/SubtitlePanel.vue       # 右侧台词卡片面板（Play/LocalPlay 共用）
├─ utils/recorder.js # 录音：AudioContext 采 16k PCM + 前端封 WAV 头
├─ utils/srt.js      # SRT 解析（容错：BOM/坏行/缺序号）
└─ utils/date.js     # 日期工具
```

无 UI 组件库、无日历库、无播放器库——四页面的量级，原生控件 + 自写 CSS 更小更快。

顶栏（App.vue）：品牌、「自由播放」入口、后台齿轮图标（icon-btn，无文字标签）。

### 双向时间轴绑定（核心交互，Play.vue）

- **video → sentence**：`timeupdate` 事件里二分/线性找 `start ≤ t < end` 的句子，命中则高亮 + `scrollIntoView({block:'nearest'})`
- **sentence → video**：点击句子 `video.currentTime = start` 并 `play()`
- 已完成打卡按钮：手动触发 checkin（POST `/api/day/{date}/checkin`），后端 `INSERT OR IGNORE` 幂等兜底；不再依赖播放进度（看到哪算哪，由用户点按钮确认）

### 视频加载与字幕（Play 与 LocalPlay 同一套规则）

- 加载视频时同时取**同目录同名**的 `.srt` 与 `.json`：srt 经 `utils/srt.js` 解析为 cues，`SubtitleOverlay` 内嵌在视频底部随播放显示，`SubtitleStylePicker` 切换预设样式（清晰/影院/黑底/关闭，默认清晰）；json 按字幕契约解析为 sentences，`SubtitlePanel` 渲染右侧台词区
- Play 数据来自 `/api/day`（`srtUrl` → `/api/materials/{id}/srt`）；LocalPlay（`/local`）用 `input[webkitdirectory]` 选本地文件夹，从同一 FileList 找同名 srt/json，视频走 ObjectURL（换视频时 revoke）；不做打卡与跟读
- 一天多素材：Play 标题下方 chips 按素材自然序切换（= 导入时文件名序号），字幕面板/跟读随当前素材；打卡仍按天，首次打卡顺带把这些素材标已读

### 跟读录音交互（已实现，Play.vue + utils/recorder.js）

- 每句卡片提供"跟读"按钮：点击开始/停止录音；**直接录 WAV（16k/16bit/单声道）**——`AudioContext({sampleRate:16000})` 采 PCM、前端封 WAV 头（所有候选云 API 都不收 webm，别用 MediaRecorder 默认格式）
- 停止后自动 `FormData(audio, reference=句子en)` 上传 `/api/score`，期间按钮显示评分中（评分秒级，需防重复提交）
- 结果渲染：句级三分数（准确/流利/完整）+ 逐词着色（好/中/差三档）+ 点词展开 expected/actual 音素对比
- 录音期间暂停视频播放（避免视频声音混入麦克风）；评分失败 toast 提示，不影响页面其他功能

### Dev/Prod 一致性

- dev：`vite.config.js` proxy `/api` → `127.0.0.1:8420`；`MOCK=1` 时 `mockApiPlugin.js` 在 dev server 内拦截 `/api` 返回假数据，可纯前端独立开发
- prod：`npm run build` 产出 dist，后端 SPA fallback（非 `/api` 未知路径回落 index.html，且防目录穿越）

## 7. 验证体系

- `backend/smoke_test.py`：自包含冒烟（起真实服务 → 96 断言 → finally 清理临时 db/素材目录，scoring.json / library.json 快照还原）：统一前缀读写（含 422）、课程导入（素材自然排序 10.omega 在 4.delta 后 / 子文件夹与非 mp4 忽略 / 坏字幕 skipped 不占位 / 重导幂等 id 不变 / 相对路径 / 前缀外与不存在 422 / 消失文件保留）、课程列表与详情形状（materialCount/readCount/dates/readAt/sentenceCount）、排课（5 素材/4 天=2-1-1-1、3 素材/6 天=前 3 天各 1 后留空、单天全排、叠加 added=0、跨月、404、日期倒序与格式 422）、月度排期视图、逐天补素材（计数/叠加/未知 id/空数组 422）、清空当天与移除单素材（removed 计数、422、空天清打卡）、删素材/删课程级联计数与孤儿打卡清理、已读切换（true 置时间、幂等、false 置 NULL、打卡补读且手动已读保留原时间）、calendar/day 形状与排序、Range 206+Content-Range、srt 端点（去 BOM）与 404、SPA 托管与 fallback、评分链路（mock provider）、scoring 配置读写
- `frontend/src/tests/*.spec.js`（vitest + happy-dom）6 文件 19 例：日历渲染、句子高亮、点击 seek、跟读评分结果、录音 WAV 封装、课程导入（含覆盖标签）、SRT 解析、多素材切换、字幕样式、本地播放流程
- `frontend/smoke-dev.mjs`：dev server + MOCK 冒烟（mock 含 /api/score、scoring 配置、课程导入、srt、/local 页壳）
- echoic：`providers/unisound_test.py` 离线自测（真实 API 需密钥，已单独用真实密钥人工验收）

## 8. 已知边界

- 并发写 SQLite 靠短事务 + WAL 默认配置，单用户无风险；多用户需重估（非目标）
- 素材存相对路径 + 统一前缀：整个素材库挪盘只改 `data/library.json` 的 root；文件挪走后播放 404，重导同目录即可修复并保留 id
- 旧模型（videos / books+day_books）数据不迁移——库为空，启动即新 schema（courses/materials/day_materials），并在 `init_db()` 丢弃遗留的 `books`/`day_books` 表
- 同一个文件在库内挪动位置 = `rel_path` 变了 = 新素材（旧条目留在库里需手动删），改名同理
- 导入不递归：只取所选文件夹的直接子级 `*.mp4`，更深的层级建子文件夹当独立课程导入
- 素材数 < 排课天数时不报错，前 n 天各 1、后面留空（之后可在打卡管理里逐天补）
- 统一前缀未配置时 `/api/materials/{id}/stream` 与课程导入一律 422（需先在通用设置里设 root）
- `/local` 文件夹选择依赖 `input[webkitdirectory]`：Chrome/Edge 支持，Firefox 不支持（单机自用，默认 Chromium 系即可）
- 一天多素材时移除其中一条不影响打卡；仅当当天因此变空才连带删当天打卡
- `vue-router@5` / `vite@8` 均为当前 major，锁版本在 package.json caret 范围内
- 评分走云 API：需外网，断网时跟读评分不可用（其余功能不受影响，mock provider 可兜底联调）
- 各厂商分数分布不同，换 provider 后观感会变——首版评分不落库，影响仅当次会话
