# AGENTS.md

面向 AI 编码代理的仓库指南。

## 项目结构

`en-learn` — 英语学习应用(单机自用,无登录无云端),单仓三部分;需求与设计文档在 `docs/`(design.md 有架构图与路由说明):

- `backend/main.py` — 宿主后端,单文件 FastAPI + SQLite(`data/enlearn.db`),视频/字幕/打卡管理,`start.bat` 一键启动(端口 8420)
- `backend/echoic/` — **发音评分对接壳**:统一入口 `score_recording()` + provider 注册表(协议 + mock),供宿主接云 API。**尚未接入 main.py**(规划中的 `/api/score`;首版评分不落库,见 docs/requirements.md 非目标)。选型与架构见 `docs/scoring-api-research.md`、`docs/scoring-provider-design.md`
- `frontend/` — Vue 3 SPA(Vite + vue-router + vitest),构建产物 `frontend/dist/` 由宿主后端托管(未构建时返回提示)

工作环境:`backend/.venv`(Python 3.10+,venv 在 backend 下,勿放根目录),依赖见 `backend/requirements.txt`,`start.bat` 首次运行自动安装。**无 lint/CI/格式化工具**。

验证手段:
- 后端全 API 冒烟:`backend\.venv\Scripts\python.exe backend\smoke_test.py` — 自起服务、自带数据、自动清理。**会删除重建 `data/enlearn.db`,别在有真实数据的库上跑**
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

available_providers()  # ["mock"] — 供后台配置页做下拉
```

约定:
- 每家 API 一个 `ScoringProvider` 子类(`echoic/providers/`),`name` 是注册表键,实现在 `providers/__init__.py` 登记一行
- 网络/认证错误抛带原因的异常(宿主映射 5xx);参考词没念出来计低分不报错
- **分数是厂商原始校准分,不做二次变换**(旧本地栈的 0.25 幂校准已废弃);换 provider 分数不可比
- `import echoic` 要求 `backend/` 在 sys.path(运行 `backend/main.py` 天然满足;独立脚本需自行处理)

### 结构

```
echoic/__init__.py       # 入口 score_recording + re-export
echoic/schemas.py        # ScoringResult / WordScore(0–100)
echoic/providers/base.py # ScoringProvider 协议 + 注册表
echoic/providers/mock.py # 固定分数假 provider(联调/冒烟)
```

## 关键坑

- **requirements.txt 只写 ASCII**:pip 在中文 Windows 按 GBK 解码该文件,中文注释会直接 UnicodeDecodeError。

- **前端录音直接录 WAV(16k/16bit/单声道),别用 MediaRecorder 默认的 webm**——所有候选云 API 都不收 webm,录 WAV 后后端零转码、无 ffmpeg 依赖。
- 手动起后端调试时设 `ENLEARN_NO_BROWSER=1`,否则启动 1.5 秒后自动开浏览器。
- `main.py` 所有路径由 `__file__` 推导,与 cwd 无关;`backend/data/enlearn.db` 是历史残留,真实库在根 `data/`。
