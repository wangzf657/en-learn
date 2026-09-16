# AGENTS.md

面向 AI 编码代理的仓库指南。

## 项目结构

`en-learn` — 英语学习应用(单机自用,无登录无云端),单仓三部分;需求与设计文档在 `docs/`(design.md 有架构图与路由说明):

- `backend/main.py` — 宿主后端,单文件 FastAPI + SQLite(`data/enlearn.db`),**课程 → 素材 + 打卡管理 + 通用设置**。统一前缀存 `data/library.json`(`{"root": 绝对路径}`,缺失/损坏回落空串;`GET/PUT /api/admin/library`,未配置时导入/流式 422);课程导入 `POST /api/admin/courses/import`(`{folder}`:课程=文件夹本身,只取直接子级 `*.mp4` 不递归、按文件名自然排序,标题去 `1.`/`01_`/`001-` 前缀,同名 `.json` 作字幕,坏字幕进 skipped 不占位;幂等键 `rel_path`——重导 UPDATE id 稳定,消失的文件保留不删);课程管理 `GET /api/admin/courses`、`GET /api/admin/courses/{id}`、`DELETE /api/admin/courses/{id}`(级联删素材+排期+清空天打卡)、`DELETE /api/admin/materials/{id}`、`PUT /api/admin/materials/{id}/read`(已读状态机,只填 NULL);打卡管理 `POST /api/admin/schedule`(`{courseId,dateFrom,dateTo}`,素材自然排序按天均分,n<d 时前 n 天各 1 后留空,可跨月,叠加幂等)、`GET /api/admin/schedule?month`、`DELETE /api/admin/schedule?month`(清空当月排期+打卡)、`POST /api/admin/day/{date}/materials`、`DELETE /api/admin/day/{date}`、`DELETE /api/admin/day/{date}/materials/{materialId}`;消费端 `/api/calendar`、`/api/day/{date}`、`POST /api/day/{date}/checkin`(按天打卡幂等,首次打卡把当天素材置已读);流/字幕 `GET /api/materials/{id}/stream|srt`;跟读评分 `/api/score` 与评分配置 `GET/PUT /api/admin/scoring`,`start.bat` 一键启动(端口 8420)
- `backend/echoic/` — **发音评分对接壳**:统一入口 `score_recording()` + provider 注册表,**已上线 mock + unisound(云知声)**,经宿主 `/api/score` 接入,真实密钥配置在 `data/scoring.json`(Admin 页可改,即时生效)。选型与架构见 `docs/scoring-api-research.md`、`docs/scoring-provider-design.md`
- `frontend/` — Vue 3 SPA(Vite + vue-router + vitest),构建产物 `frontend/dist/` 由宿主后端托管(未构建时返回提示)

工作环境:`backend/.venv`(Python 3.10+,venv 在 backend 下,勿放根目录),依赖见 `backend/requirements.txt`,`start.bat` 首次运行自动安装。**无 lint/CI/格式化工具**。

验证手段:
- 后端全 API 冒烟:`backend\.venv\Scripts\python.exe backend\smoke_test.py` — 自起服务、自带数据、自动清理,**覆盖统一前缀读写、课程导入(自然排序/子文件夹忽略/坏字幕跳过/重导幂等/消失文件保留)、排课均分与留空、逐天增删、素材已读状态机、删素材/删课程级联、打卡置已读、Range 206、srt、评分链路**。**会删除重建 `data/enlearn.db` 并在 finally 还原 `library.json`/`scoring.json`,别在有真实数据的库上跑**
- 前端组件测试:`frontend/` 下 `npm test`(vitest)
- 前端 mock 冒烟:`frontend/` 下 `node smoke-dev.mjs`(自设 `MOCK=1`,无需后端)

## 前端开发

- `npm run dev` 起 Vite(5173),`/api` 代理到 `127.0.0.1:8420`;设 `MOCK=1` 改走 `mockApiPlugin.js` 内存 mock,后端不用起

## echoic 评分包

云 API 对接壳(本地模型栈已整体移除,决策与调研见 docs/scoring-api-research.md)。

### 入口(库的公开 API)

```python
from echoic import score_recording, available_providers

# 评分:用户录音 vs 参考文本;provider 名与 options 由宿主从后台配置读出传入
result = score_recording("attempt.wav", reference_text="Hello world", provider="mock")
result.model_dump()  # JSON-ready: accuracy/fluency/completeness_score + word_scores

available_providers()  # ["mock", "unisound"] — 供后台配置页做下拉
```

约定:
- 每家 API 一个 `ScoringProvider` 子类(`echoic/providers/`),`name` 是注册表键,实现在 `providers/__init__.py` 登记一行
- 网络/认证错误抛带原因的异常(宿主映射 5xx);参考词没念出来计低分不报错
- **分数是厂商原始校准分,不做二次变换**(旧本地栈的 0.25 幂校准已废弃);换 provider 分数不可比
- **unisound(云知声)硬约定**:multipart 字段顺序必须 `text→mode→voice`;词级/音素分是 0–10 制需 ×10 归一;mode 默认 E;鉴权 header `appkey: AppKey@AppSecret` + `session-id`(uuid)
- `import echoic` 要求 `backend/` 在 sys.path(运行 `backend/main.py` 天然满足;独立脚本需自行处理)

### 结构

```
echoic/__init__.py       # 入口 score_recording + re-export
echoic/schemas.py        # ScoringResult / WordScore(0–100)
echoic/providers/base.py # ScoringProvider 协议 + 注册表
echoic/providers/mock.py # 固定分数假 provider(联调/冒烟)
echoic/providers/unisound.py # 云知声 sacalleval HTTP API(线上 provider)
```

## 关键坑

- **requirements.txt 只写 ASCII**:pip 在中文 Windows 按 GBK 解码该文件,中文注释会直接 UnicodeDecodeError。**start.bat 同理只写 ASCII**:cmd 在 `chcp 65001` 后解析含中文的 bat 有字节偏移 bug,会把 echo 的中文切成碎片当命令执行。

- **素材/课程存相对路径 + 统一前缀**:整个素材库挪盘只改 `data/library.json` 的 `root`;库内挪动/改名文件 = `rel_path` 变了 = 新素材(旧条目要手动删)。未配置 root 时导入与 `/api/materials/{id}/stream` 一律 422。
- **前端录音直接录 WAV(16k/16bit/单声道),别用 MediaRecorder 默认的 webm**——所有候选云 API 都不收 webm,录 WAV 后后端零转码、无 ffmpeg 依赖。
- 手动起后端调试时设 `ENLEARN_NO_BROWSER=1`,否则启动 1.5 秒后自动开浏览器。
- `main.py` 所有路径由 `__file__` 推导,与 cwd 无关;`backend/data/enlearn.db` 是历史残留,真实库在根 `data/`。

## 开发要求
- **无登录无云端**:单机自用,无用户系统、无云存储、无云 API 调用
- **更新文档**:需求/设计文档在 `docs/`,开发时按需更新
