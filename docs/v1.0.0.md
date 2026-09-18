# EnLearn V1.0 · 需求与设计

> 英语学习应用：每日视频 + 双语字幕 + 跟读练习（TTS 朗读 + 发音评分）+ 打卡。
> 单机自用：无登录、无云端、无多用户；Windows 双击即用。

## 1. 定位与范围

**目标**
- 本地英语视频做每日精听：日历即入口，排课到天，打卡养成习惯；另有「自由播放」随意点播本地文件夹视频
- 双语字幕以自定义 JSON 维护（含重点词/笔记），逐句对照
- 跟读练习闭环：TTS 示范 → 录音 → 音素级评分即时反馈
- 零配置发布：`build.bat` → 单文件 exe

**非目标（明确不做）**：多用户/权限、在线视频、移动端适配、字幕自动生成（ASR）、复习/艾宾浩斯算法、评分历史/趋势统计（评分不落库）。

**典型流程**
1. 日历点当天 → 播放视频（自绘控制条 + 快捷键）
2. 右侧台词面板跟随高亮；点时间戳重播某句
3. 点台词卡片 → 跟读弹窗：点词块/断句听 TTS 示范，空格录音，看评分
4. 「已完成打卡」→ 回日历看到勾

自由播放：顶栏入口 → 选本地文件夹 → 点播；字幕/台词规则一致，不计打卡、不做跟读。

## 2. 功能

### 日历与打卡
- 当月日历、月份切换；有排期日期显示首条素材标题（多条显示数量），点击进入播放页
- 打卡按天幂等、明显勾标记；手动触发，不依赖播放进度；无自动打卡
- 首次打卡顺带把当天素材置已读（手动已读的保留原时间）；当天无任务时播放页给出提示

### 视频播放
- 本地视频服务端流式（HTTP Range 拖动进度）；自绘控制条：播放/暂停、进度、音量、倍速 0.5–2x、全屏
- 快捷键：`Space` 播放/暂停、`Enter` 收起/展开台词抽屉、`F11` 全屏（跟读弹窗打开时全部失效；输入框聚焦时不拦截）
- 一屏固定不滚动：视频区 + 右侧台词抽屉各自内滚；宽屏视频保持 16:9 等比；进入全屏自动收起抽屉
- 底部字幕浮层：4 样式（清晰/影院/黑底/关闭）× 3 档字号，localStorage 持久化；优先用内存 JSON 字幕，无则回退解析 srt
- 一天多素材：控制条 chips 按自然序切换

### 学习面板与时间轴
- 台词卡片：英文 + 中文；当前句自动高亮并滚动居中
- video → 句子高亮（`start ≤ t < end`，播过末句保持末句）；句子时间戳按钮 → seek 并播放（越过句尾不自动暂停）
- Play 页整卡点击打开跟读弹窗；自由播放页整卡点击 = seek
- 词块/笔记收敛进跟读弹窗展示，面板卡片不渲染

### 跟读练习弹窗
- 一屏布局：左 30% 学习区（词块 + 按标点断句的短句块，点击 = 填入文本框 + TTS 朗读，再点停止）+ 右 70% 练习区（参考文本可自由编辑、朗读、录音评分）
- TTS 四种条目互斥朗读：整句 / 词块 / 断句 / 自定义文本
- 录音：按钮或空格键一键开始/停止，可回放本次录音；WAV 16k/16bit/单声道直传 `/api/score`
- 评分展示：总分 + 五星 + 等级；三维进度条（准确/流利/完整）；ASR 对比（标准文本 vs 实际读出，未识别到人声时提示）；音质徽章（音量偏小/削波/噪声/截断/过短/空音频）；逐词三档着色 + 词类型徽章（漏/错/多）+ 重音对错 + 逐音素着色
- 失败（麦克风拒绝/空音频/对齐失败）弹窗内提示，不阻塞页面；结果只活当次会话，关闭即弃

### TTS 朗读与选声
- 浏览器原生 `speechSynthesis`，零依赖；后台可配本机英语音色（标注 联网/本地）+ 语速（默认 0.9），试听 + 保存（localStorage）
- 预热：启动与切换音色时用零音量 utterance 触发引擎初始化并 `resume()`，规避 Chrome 闲置后首句不出声

### 后台管理
- **通用设置**：统一前缀（素材库根目录，存 `data/library.json`，未配置时导入/播放不可用）；发音评分服务（provider 下拉 + unisound 密钥/mode/base_url，存 `data/scoring.json`，即时生效）；浏览器端选声
- **课程管理**：导入（前缀内文件夹 → 直接子级 `*.mp4` 自然排序，同名 `.json` 作字幕；重导幂等、id 稳定；坏字幕跳过不占位；消失文件保留不删）；列表/详情/删除（级联清素材、排期与孤儿打卡）；素材手动已读
- **打卡管理**：排课（选课程 + 日期区间，素材按天均分，不足留空，可叠加）；月度排期视图；逐天补/删素材；清空某天/当月（连带打卡）

## 3. 架构与关键取舍

```
┌─ 浏览器 http://127.0.0.1:8420 ─────────────────────┐
│  Vue3 SPA（frontend/dist 静态文件）                  │
│  /            日历首页 Home.vue                      │
│  /play/:date  播放页 Play.vue（含跟读弹窗）           │
│  /local       自由播放 LocalPlay.vue（本地文件夹）    │
│  /admin       后台 Admin.vue                        │
└──────────────┬──────────────────────────────────────┘
               │ /api/*（fetch JSON / multipart）
┌──────────────▼──────────────────────────────────────┐
│  FastAPI 单进程 (backend/main.py, ~665 行)            │
│  ├─ REST API（sqlite3 标准库直连）                    │
│  ├─ 视频流 FileResponse（原生支持 Range → 206）       │
│  ├─ 跟读评分 /api/score（同步 def，线程池执行）        │
│  └─ 其余路径托管 dist 静态文件 + SPA fallback          │
└───────┬──────────────────────┬──────────────┬────────┘
        │                      │              │
  data/enlearn.db      data/library.json   backend/echoic/（云 API 对接壳）
  （SQLite 单文件）     （统一前缀 root）    统一入口 + 多 provider（mock + unisound）
```

关键取舍：

- **单端口托管前端**：生产免 nginx；dev 用 vite proxy `/api`，同一套前端代码两种环境无差异
- **sqlite3 标准库无 ORM**：四张表，每请求短连接，单用户量级足够
- **课程 → 素材两级**：课程 = 被导入的文件夹（一季/一套），素材 = 课程内 mp4 + 同名 JSON 字幕；排期与课程解耦（`day_materials` 只管"哪天学哪些"）
- **只存相对路径 + 统一前缀**：素材库挪盘只改 `data/library.json` 的 root；库内挪动/改名 = 新素材；文件移走播放 404，重导同目录修复
- **导入即唯一录入入口**：不递归、只取直接子级 `*.mp4` 按文件名自然排序（数字段按数值）；幂等键 `rel_path`（重导 UPDATE，id 稳定）；只增不删（消失文件保留）；因此不需要单条增改表单
- **排课按天均分，素材不够就留空**：n≥d 时前 extra 天 +1；n<d 时前 n 天各 1，之后可逐天补
- **素材已读单状态机**：`read_at` 可空时间戳，手动切换与首次打卡共用，打卡只填 NULL
- **原生 `<video>` + 自绘控制条**：直接调 video 元素 API，零播放器依赖；快捷键全局挂 window
- **评分走云 API，echoic 只做对接壳**：统一入口 + provider 注册表，宿主只加一个上传→调库→返回的端点，不感知厂商细节；音频在前端收敛为 WAV（云 API 均不收 webm，后端零转码）
- **评分不落库**：即时反馈定位；将来要历史只需加 `scores` 表 + 评分返回体原样入库（方向见 docs/v1.1.md）

## 4. 数据模型

```sql
courses  (id, name, rel_path UNIQUE, created_at)                    -- 课程 = 被导入的文件夹
materials(id, course_id → courses.id, title, rel_path UNIQUE,       -- 素材 = mp4 + 同名 json 字幕
          subtitle_json, read_at NULL, created_at)
day_materials(date, material_id, PRIMARY KEY(date, material_id))    -- 排期：哪天学哪些素材
checkins (date PRIMARY KEY, checked_at)                             -- 打卡（只按天）
```

- `rel_path` 相对 root（统一 `/` 分隔）；`materials.rel_path` UNIQUE 即导入幂等键
- 排期复合主键：素材可排多天、天可多素材；`INSERT OR IGNORE` 幂等可叠加
- `read_at`：NULL = 未读；手动切换与首次打卡共用（打卡只覆盖 NULL）
- 删除手动维护（不依赖外键级联）：删课程/素材 → 删对应排期 → 因此变空的天连打卡一起删
- `subtitle_json` 存规范化 JSON 字符串（`ensure_ascii=False` 保中文可读）

配置文件：`data/library.json` = `{"root": 绝对路径}`（缺失/损坏回落空串 = 未配置）；`data/scoring.json` = `{"provider", "options"}`（请求时现读，即时生效）。

数据库升级：`PRAGMA user_version` 版本戳 + `MIGRATIONS` 列表原地迁移（改表结构时 `SCHEMA_VERSION` +1 并追加迁移；迁移前自动备份 `enlearn.db.bak`；库比程序新时拒绝启动）。

## 5. API 契约

| 方法 | 路径 | 说明 | 错误 |
|---|---|---|---|
| GET/PUT | `/api/admin/library` | 统一前缀读写（`data/library.json`，原子写） | 422 目录不存在 |
| POST | `/api/admin/courses/import` | 导入课程：folder（绝对或前缀相对）下直接子级 `*.mp4` 自然排序入库，同名 `.json` 作字幕；幂等键 `rel_path`；返回 `{course, materials[], skipped[]}` | 422 未配置前缀/文件夹不存在/在前缀外 |
| GET | `/api/admin/courses` | 课程列表（id/name/materialCount/readCount/dates[]） | — |
| GET | `/api/admin/courses/{id}` | 课程详情：materials[]（title/relPath/sentenceCount/read/readAt/dates[]） | 404 |
| DELETE | `/api/admin/courses/{id}` | 级联删素材 + 排期 + 清孤儿天打卡 | 404 |
| DELETE | `/api/admin/materials/{id}` | 删素材 + 级联删排期 + 清孤儿天打卡 | 404 |
| PUT | `/api/admin/materials/{id}/read` | 已读：`{read}`→`{id,read,readAt}`；true 只在 NULL 置 now | 404 |
| POST | `/api/admin/schedule` | 排课：`{courseId,dateFrom,dateTo}`（可跨月），按天均分、不足留空、叠加幂等 | 404 课程；422 日期范围 |
| GET | `/api/admin/schedule?month` | 月度排期：`{days[]{date,checked,materials[]}}` | 422 格式 |
| DELETE | `/api/admin/schedule?month` | 清空当月排期 + 打卡 | 422 格式 |
| POST | `/api/admin/day/{date}/materials` | 逐天补素材：`{materialIds[]}`，`{added}` | 422 空/不存在 |
| DELETE | `/api/admin/day/{date}` | 清空当天排期 + 打卡 | — |
| DELETE | `/api/admin/day/{date}/materials/{materialId}` | 移除当天一条；变空则连删打卡 | 404/422 |
| GET | `/api/calendar?month` | 当月任务（date/materialId/title/checked/materialCount） | 422 格式 |
| GET | `/api/day/{date}` | 播放页数据：materials[]（title/videoUrl/srtUrl/subtitle）+ checked | 404 无排期 |
| POST | `/api/day/{date}/checkin` | 打卡幂等；首次打卡把当天素材置已读 | 404 无排期 |
| GET | `/api/materials/{id}/stream` | 视频流，支持 Range | 422 未配置前缀；404 |
| GET | `/api/materials/{id}/srt` | 同名 `.srt` 原样文本（去 BOM） | 422；404 |
| POST | `/api/score` | 跟读评分：multipart（audio + reference）→ ScoringResult | 422 缺字段；500 评分失败 |
| GET/PUT | `/api/admin/scoring` | 评分 provider 配置读写（GET 附 providers 下拉） | 422 未知 provider |

## 6. 字幕 JSON 契约

结构唯一权威（机器可读）：`.agents/skills/srt-to-json/subtitle.schema.json`——顶层 `sentences[]`，每句必填 `start/end/en`，可选 `zh/words/note`。从纯英文 SRT 生成教学 JSON 的离线流水线见 `.agents/skills/srt-to-json/SKILL.md`。

- 消费方：后端导入校验入库；前端渲染卡片/时间轴/跟读弹窗；`/api/score` 以整句 `en`（或弹窗编辑后的文本）为参考——`en` 逐字不得改写
- 校验分层（宁松勿卡，自用数据）：**硬校验**（服务端 `normalize_subtitle`：JSON 合法 + `sentences` 数组 + `start/end` 数字 + `en` 字符串，违反整条素材跳过）；**强约定**（生产方 check：`end > start`、单调不重叠、`words.w` 能在 `en` 中找到、文本守恒）；**前端容错渲染**（字段缺失/形状不对静默降级，服务端有意不校验 `zh`/`words` 结构）
- 存储与传输：`subtitle_json` 存规范化 JSON；`/api/day` 原样透传；导入读同名 `.json`（UTF-8 无 BOM，BOM 即整条跳过），缺失置空 `{"sentences":[]}`
- 时间轴语义：高亮 `start ≤ t < end`，句间空隙不高亮，播过末句保持末句
- 演进：只增可选字段（旧数据免迁移）；不改名不改语义；改结构先改 schema 再改代码
- 已知边界：句级 `note` 前端未渲染；`sentences` 顺序即渲染顺序（生产方按 `start` 升序）

## 7. 跟读评分（echoic 对接壳）

> 已上线并经真实 API 验收（2026-09）：宿主端点 `/api/score`、前端跟读弹窗、云知声 unisound provider。选型结论：放弃本地模型栈，走云 API；所有候选 API 均不收 webm → 前端直接录 WAV。

**调用链**：前端录 WAV(16k/16bit/单声道) → `POST /api/score`（multipart: audio + reference；同步 `def` 端点走线程池）→ 读 `data/scoring.json` → 存临时文件 → `echoic.score_recording()` → provider 调云 API → `ScoringResult` → 删临时文件 → JSON 返回。

```
echoic/__init__.py           # 入口 score_recording()，按 provider 名分发
echoic/schemas.py            # ScoringResult / WordScore（0–100）+ 诊断字段
echoic/providers/base.py     # ScoringProvider 协议 + 注册表（register/get/available）
echoic/providers/mock.py     # 固定分数假 provider（联调/冒烟）
echoic/providers/unisound.py # 云知声口语评测（线上 provider）
```

新增厂商三步：`ScoringProvider` 子类（类属性 `name` = 注册表键）→ `providers/__init__.py` 登记一行 → 后台配置切换。宿主约定：配置每次请求现读（改配置即时生效）；厂商异常 → 500 附原因；参考词没念出来是低分不是错误。

**结果契约**（`ScoringResult.model_dump()`）：

```json
{
  "accuracy_score": 82.5, "fluency_score": 78.0, "completeness_score": 90.0,
  "word_scores": [{
    "word": "doing", "accuracy_score": 85.0,
    "expected_phonemes": "ˈduːɪŋ", "actual_phonemes": "duːɪŋ",
    "phoneme_scores": [90.0, 80.0, 70.0], "phonemes": ["d", "uː", "ɪŋ"],
    "type": 2, "stress": 1
  }],
  "sample": "How are you doing?", "usertext": "How are you doing",
  "audio_quality": { "volume": false, "clipping": false, "noise": true, "cut": false, "too_short": false, "empty_audio": false }
}
```

- 分数是**厂商原始校准分**，直接展示不做二次换算；换 provider 分数不可比
- 诊断字段（厂商给什么透什么）：`sample`/`usertext` = ASR 识别对比；`word.type` = 0 多词 / 1 漏词 / 2 正常 / 3 错词（静音/重复/标点已滤除，漏词计 0 分）；`stress` = -1 未知 / 0 错 / 1 对；`phonemes` 与 `phoneme_scores` 对齐（逐音素着色）；`audio_quality` = audiocheck 归一（True = 检测到问题）
- unisound 硬约定：multipart 字段顺序必须 `text → mode → voice`；词级/音素分 0–10 制需 ×10 归一；mode 默认 E；鉴权 header `appkey: AppKey@AppSecret` + `session-id`(uuid)；错误码映射为中文异常

## 8. 前端设计

```
frontend/src/
├─ api.js            # 全部 fetch 封装（与后端契约逐字对齐）
├─ views/Home.vue    # 日历：当月网格、月份切换、打卡标记
├─ views/Play.vue    # 播放页核心（一屏固定布局、自绘控制条、快捷键）
├─ views/LocalPlay.vue # /local 自由播放：选本地文件夹点播（卡片点击 = seek）
├─ views/Admin.vue   # 后台：课程管理 + 打卡管理 + 通用设置（前缀/评分服务/选声）
├─ components/RepeatModal.vue        # 跟读练习弹窗（词块/断句 + TTS + 录音评分）
├─ components/SubtitleOverlay.vue     # 视频底部字幕浮层（timeupdate 匹配）
├─ components/SubtitleStylePicker.vue # 字幕样式切换（4 样式 × 3 字号）
├─ components/SubtitlePanel.vue       # 右侧台词卡片面板（cardAction 区分点击行为）
├─ utils/recorder.js # 录音：AudioContext 采 16k PCM + 前端封 WAV 头
├─ utils/tts.js      # speechSynthesis 封装（音色枚举/持久化/预热）
├─ utils/srt.js      # SRT 解析（容错：BOM/坏行/缺序号）
└─ utils/date.js     # 日期工具
```

- 无 UI/日历/播放器库——原生控件 + 自写 CSS；顶栏（App.vue）：品牌、「自由播放」、后台齿轮
- 跟读弹窗：`fixed inset 0` 遮罩；卡片 `height: min(880px, 100svh - 32px)` 不滚动，左学习区/右侧逐词列表各自内滚；录音状态机 `idle → starting（可取消）→ recording → scoring → result / error`；录音 Blob 可回放（关闭/覆盖时 `revokeObjectURL`）
- 浮层字幕 cue 优先从内存 sentences 派生，无 JSON 时才 fetch srt 兜底（请求序号丢弃迟到响应）
- Dev/Prod 一致性：dev `MOCK=1` 走 `mockApiPlugin.js` 内存 mock；prod 后端 SPA fallback（防目录穿越）

## 9. 部署与打包

- 双击根目录 `build.bat` 一键构建（装依赖 → `npm run build` → PyInstaller onefile）→ 单文件 `release\EnLearn.exe`；拷到任意 Win10+ 机器双击运行，首启在 exe 旁生成 `data\`，浏览器自动打开；冷启动解包约 2–3 秒
- 端口 8420，仅本机 127.0.0.1；无外部服务依赖
- 调试时设 `ENLEARN_NO_BROWSER=1` 可禁自动开浏览器

## 10. 验证体系

- `backend/smoke_test.py`：自起服务全 API 冒烟（103 项检查，覆盖导入/排课/已读/级联/422/Range 206/srt/评分链路/配置读写；会重建 `data/enlearn.db` 并快照还原 library/scoring.json——**勿在有真实数据的库上跑**）
- 前端：`npm test`（vitest + happy-dom，8 文件 44 例：日历、高亮/seek、跟读弹窗全流程、录音 WAV、字幕样式、后台表单、本地播放）；`npm run build` 零错误
- `frontend/smoke-dev.mjs`：MOCK=1 dev server 冒烟
- `backend/echoic/providers/unisound_test.py`：离线自测（真实 API 已用密钥人工验收）

## 11. 已知边界

- SQLite 单用户量级（短连接 + 默认配置），多用户需重估（非目标）
- 素材存相对路径 + 统一前缀：挪库只改 root；文件挪走播放 404，重导同目录修复并保留 id；库内移动/改名 = 新素材
- 导入不递归：更深层级建子文件夹当独立课程导入
- 素材数 < 排课天数不报错，前 n 天各 1、后面留空（可逐天补）
- 统一前缀未配置时 `/api/materials/{id}/stream` 与导入一律 422
- `/local` 文件夹选择依赖 `input[webkitdirectory]`：Chrome/Edge 支持，Firefox 不支持
- 一天多素材移除其中一条不影响打卡；仅当天变空才连带删打卡
- 评分走云 API：需外网，断网时跟读评分不可用（其余功能不受影响）；换 provider 分数分布不同；评分不落库，影响仅当次会话
- `vue-router@5` / `vite@8` 为当前 major，锁在 package.json caret 范围内
