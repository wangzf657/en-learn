# EnLearn 设计文档

## 1. 总体架构

单进程单端口，无前后端分离部署：

```
┌─ 浏览器 http://127.0.0.1:8420 ─────────────────────┐
│  Vue3 SPA（frontend/dist 静态文件）                  │
│  /            日历首页 Home.vue                      │
│  /play/:date  播放页 Play.vue                       │
│  /admin       后台 Admin.vue                        │
└──────────────┬──────────────────────────────────────┘
               │ /api/*（fetch JSON）
┌──────────────▼──────────────────────────────────────┐
│  FastAPI 单进程 (backend/main.py, ~290 行)            │
│  ├─ REST API（sqlite3 标准库直连）                    │
│  ├─ 视频流 FileResponse（原生支持 Range → 206）       │
│  └─ 其余路径托管 dist 静态文件 + SPA fallback          │
└──────────────┬──────────────────────────────────────┘
               │
        data/enlearn.db（SQLite 单文件）
```

**关键取舍**：
- **单端口托管前端**：生产免 nginx，dev 用 vite proxy `/api`，同一套前端代码两种环境无差异
- **sqlite3 标准库无 ORM**：表就两张，ORM 纯属负担；每请求短连接（`closing(db())`），单用户量级足够
- **视频不复制入库，只存路径**：视频文件大且已有，流式接口按 id 查路径后 `FileResponse`；文件被移走时播放返回 404，后台有 validate-path 提前验证
- **原生 `<video>` 而非 video.js**：倍速/暂停/进度全是浏览器自带能力，零依赖满足需求

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

## 5. 前端设计

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

### Dev/Prod 一致性

- dev：`vite.config.js` proxy `/api` → `127.0.0.1:8420`；`MOCK=1` 时 `mockApiPlugin.js` 在 dev server 内拦截 `/api` 返回假数据，可纯前端独立开发
- prod：`npm run build` 产出 dist，后端 SPA fallback（非 `/api` 未知路径回落 index.html，且防目录穿越）

## 6. 验证体系

- `backend/smoke_test.py`：自包含冒烟（起真实服务 → 20 断言 → finally 清理临时 db/mp4）：CRUD、409/422、Range 206+Content-Range、打卡幂等、SPA 托管、fallback、级联删除
- `frontend/src/tests/*.spec.js`（vitest + happy-dom）4 例：日历渲染、句子高亮、点击 seek、后台表单校验
- `frontend/smoke-dev.mjs`：dev server + MOCK 冒烟

## 7. 已知边界

- 并发写 SQLite 靠短事务 + WAL 默认配置，单用户无风险；多用户需重估（非目标）
- 视频路径为绝对路径存库，文件挪走即 404（有 validate-path 缓解）
- `vue-router@5` / `vite@8` 均为当前 major，锁版本在 package.json caret 范围内
