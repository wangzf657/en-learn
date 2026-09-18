# EnLearn

> 单机自用的英语学习应用：把本地英语视频做成每日精听课程——日历排课、双语字幕、跟读发音评分、打卡。

## 功能

- **日历排课 + 打卡**：导入课程后素材按天均分排期；打卡按天幂等，首次打卡把当天素材置已读
- **视频播放**：一屏固定布局、自绘控制条（倍速/全屏/快捷键）、底部字幕浮层 4 样式 × 3 字号
- **双语台词面板**：自定义 JSON 教学字幕（重点词/断句/笔记），当前句高亮，点时间戳重播
- **跟读练习**：TTS 示范朗读 → 录音 → 音素级评分（准确/流利/完整 + 逐词逐音素 + ASR 对比 + 音质检测）
- **自由播放**：直接点播本地任意文件夹里的视频，字幕规则一致，不计打卡
- **后台管理**：素材库前缀、课程导入、排课调整、评分服务（云知声）与浏览器音色配置

## 快速开始

```powershell
# 后端（Python 3.10+）
python -m venv backend/.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python backend\main.py          # http://127.0.0.1:8420

# 前端（Node + Vue3/Vite）
cd frontend
npm install
npm run dev                                            # http://127.0.0.1:5173，/api 代理到 8420
# MOCK=1 npm run dev → 走内置 mock，无需后端
```

首次使用：后台「通用设置」设置素材库根目录 → 「课程管理」导入课程文件夹 → 「打卡管理」排课。
跟读评分需在「通用设置 · 发音评分服务」填入云知声 AppKey / Secret。

### 打包发布

```powershell
build.bat
```

产出 `release\EnLearn.exe`（单文件），拷到任意 Win10+ 机器双击运行；首次启动在 exe 旁生成 `data\` 目录。

## 测试

```powershell
backend\.venv\Scripts\python backend\smoke_test.py    # 后端全 API 冒烟（勿在有真实数据的库上跑）
cd frontend && npm test                                # 前端组件测试（vitest）
```

## 文档

- [docs/design.md](docs/design.md) — V1.0 需求与设计（唯一文档：功能、架构、API 契约、部署、验证）
- [docs/v1.1.md](docs/v1.1.md) — V1.1 迭代方向（评分落库、听写模式……）

## 技术栈

FastAPI + SQLite（标准库 sqlite3，无 ORM） · Vue 3 + Vite（无 UI/播放器库） · 浏览器原生 video / speechSynthesis · 评分对接壳 `backend/echoic/`（mock + unisound）
