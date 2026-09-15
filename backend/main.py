import json
import os
import re
import sqlite3
import tempfile
import threading
import webbrowser
from contextlib import closing
from calendar import monthrange
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from echoic import available_providers, score_recording

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "enlearn.db"
SCORING_PATH = DATA_DIR / "scoring.json"
DIST = ROOT / "frontend" / "dist"

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  video_path TEXT NOT NULL,
  subtitle_json TEXT NOT NULL DEFAULT '{"sentences":[]}',
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS checkins (
  date TEXT PRIMARY KEY,
  video_id INTEGER NOT NULL,
  checked_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

app = FastAPI(title="EnLearn")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    with closing(db()) as conn, conn:
        conn.executescript(SCHEMA)


def scoring_config() -> dict:
    """读评分 provider 配置;文件缺失/损坏时回落 mock。每次请求现读,改配置即时生效。"""
    try:
        with open(SCORING_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"provider": "mock", "options": {}}
    if not isinstance(cfg, dict):
        return {"provider": "mock", "options": {}}
    return {"provider": cfg.get("provider", "mock"), "options": cfg.get("options") or {}}


def valid_date(s: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def normalize_subtitle(raw) -> str:
    """校验并规范化字幕 JSON，非法时抛 422。返回规范化后的 JSON 字符串。"""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(422, "subtitleJson 不是合法 JSON")
    if not isinstance(data, dict) or not isinstance(data.get("sentences"), list):
        raise HTTPException(422, "subtitleJson 必须是包含 sentences 数组的对象")
    for s in data["sentences"]:
        if not isinstance(s, dict):
            raise HTTPException(422, "sentences 元素必须是对象")
        if not isinstance(s.get("start"), (int, float)) or not isinstance(
            s.get("end"), (int, float)
        ) or not isinstance(s.get("en"), str):
            raise HTTPException(422, "每句必须包含 start/end(数字) 和 en(字符串)")
    return json.dumps(data, ensure_ascii=False)


@app.get("/api/calendar")
def calendar(month: str):
    if not re.fullmatch(r"\d{4}-\d{2}", month or ""):
        raise HTTPException(422, "month 格式应为 YYYY-MM")
    with closing(db()) as conn, conn:
        rows = conn.execute(
            "SELECT v.id, v.date, v.title, c.date AS checked_date "
            "FROM videos v LEFT JOIN checkins c ON c.date = v.date "
            "WHERE v.date LIKE ? ORDER BY v.date",
            (month + "-%",),
        ).fetchall()
    return {
        "days": [
            {
                "date": r["date"],
                "videoId": r["id"],
                "title": r["title"],
                "checked": r["checked_date"] is not None,
            }
            for r in rows
        ]
    }


@app.get("/api/day/{date}")
def get_day(date: str):
    if not valid_date(date):
        raise HTTPException(422, "date 格式应为 YYYY-MM-DD")
    with closing(db()) as conn, conn:
        r = conn.execute("SELECT * FROM videos WHERE date = ?", (date,)).fetchone()
        if not r:
            raise HTTPException(404, "当天没有学习任务")
        checked = (
            conn.execute("SELECT 1 FROM checkins WHERE date = ?", (date,)).fetchone()
            is not None
        )
    return {
        "videoId": r["id"],
        "title": r["title"],
        "videoUrl": f"/api/videos/{r['id']}/stream",
        "checked": checked,
        "subtitle": json.loads(r["subtitle_json"]),
    }


@app.post("/api/day/{date}/checkin")
def checkin(date: str):
    if not valid_date(date):
        raise HTTPException(422, "date 格式应为 YYYY-MM-DD")
    with closing(db()) as conn, conn:
        r = conn.execute("SELECT id FROM videos WHERE date = ?", (date,)).fetchone()
        if not r:
            raise HTTPException(404, "当天没有学习任务")
        conn.execute(
            "INSERT OR IGNORE INTO checkins(date, video_id) VALUES (?, ?)",
            (date, r["id"]),
        )
    return {"ok": True}


@app.get("/api/videos/{vid}/stream")
def stream(vid: int):
    with closing(db()) as conn, conn:
        r = conn.execute("SELECT video_path FROM videos WHERE id = ?", (vid,)).fetchone()
    if not r:
        raise HTTPException(404, "视频不存在")
    path = Path(r["video_path"])
    if not path.is_file():
        raise HTTPException(404, f"视频文件不存在: {path}")
    return FileResponse(path, media_type="video/mp4")


class ScoringConfigIn(BaseModel):
    provider: str
    options: dict = {}


class ImportIn(BaseModel):
    path: str
    month: str


@app.get("/api/admin/videos")
def admin_list():
    with closing(db()) as conn, conn:
        rows = conn.execute(
            "SELECT v.*, c.date AS checked_date FROM videos v "
            "LEFT JOIN checkins c ON c.date = v.date ORDER BY v.date DESC"
        ).fetchall()
    videos = []
    for r in rows:
        try:
            n = len(json.loads(r["subtitle_json"]).get("sentences", []))
        except (json.JSONDecodeError, AttributeError):
            n = 0
        videos.append(
            {
                "id": r["id"],
                "date": r["date"],
                "title": r["title"],
                "videoPath": r["video_path"],
                "sentenceCount": n,
                "checked": r["checked_date"] is not None,
            }
        )
    return {"videos": videos}


@app.delete("/api/admin/videos/{vid}")
def admin_delete(vid: int):
    with closing(db()) as conn, conn:
        cur = conn.execute("DELETE FROM videos WHERE id = ?", (vid,))
        if cur.rowcount == 0:
            raise HTTPException(404, "视频不存在")
        conn.execute("DELETE FROM checkins WHERE video_id = ?", (vid,))
    return {"ok": True}


@app.post("/api/admin/videos/import")
def admin_import_videos(body: ImportIn):
    if not re.fullmatch(r"\d{4}-\d{2}", body.month or ""):
        raise HTTPException(422, "month 格式应为 YYYY-MM")
    try:
        datetime.strptime(body.month, "%Y-%m")
    except ValueError:
        raise HTTPException(422, "month 格式应为 YYYY-MM")
    year, mon = int(body.month[:4]), int(body.month[5:7])
    days_in_month = monthrange(year, mon)[1]
    folder = Path(body.path)
    if not folder.is_dir():
        raise HTTPException(422, "文件夹不存在")

    pattern = re.compile(r"^(\d{1,2})_(.+)\.mp4$", re.IGNORECASE)
    with closing(db()) as conn, conn:
        existing = {
            r["date"]
            for r in conn.execute(
                "SELECT date FROM videos WHERE date LIKE ?", (body.month + "-%",)
            )
        }
        seen = set()
        imported, skipped = [], []
        for entry in sorted(folder.iterdir(), key=lambda p: p.name):
            if not entry.is_file():
                continue
            m = pattern.match(entry.name)
            if not m:
                continue  # 不匹配文件名模式,直接忽略
            day = int(m.group(1))
            if day < 1 or day > days_in_month:
                skipped.append((day, {"file": entry.name, "reason": "序号超出当月天数"}))
                continue
            date = f"{body.month}-{day:02d}"
            subtitle = '{"sentences":[]}'
            sub_file = folder / (entry.stem + ".json")
            if sub_file.is_file():
                try:
                    subtitle = normalize_subtitle(sub_file.read_text(encoding="utf-8"))
                except (HTTPException, OSError, UnicodeDecodeError):
                    skipped.append((day, {"file": entry.name, "reason": "字幕 JSON 无效"}))
                    continue
            title, video_path = m.group(2), str(entry.resolve())
            if date in existing or date in seen:
                conn.execute(
                    "UPDATE videos SET title = ?, video_path = ?, subtitle_json = ? WHERE date = ?",
                    (title, video_path, subtitle, date),
                )
                vid = conn.execute(
                    "SELECT id FROM videos WHERE date = ?", (date,)
                ).fetchone()["id"]
                updated = date in existing
            else:
                cur = conn.execute(
                    "INSERT INTO videos(date, title, video_path, subtitle_json) VALUES (?, ?, ?, ?)",
                    (date, title, video_path, subtitle),
                )
                vid = cur.lastrowid or 0
                updated = False
            imported.append({"id": vid, "date": date, "title": title, "updated": updated})
            seen.add(date)
    imported.sort(key=lambda v: v["date"])
    skipped.sort(key=lambda t: t[0])
    return {"imported": imported, "skipped": [d for _, d in skipped]}


@app.post("/api/score")
def score(audio: UploadFile = File(...), reference: str = Form(...)):
    cfg = scoring_config()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    try:
        with tmp:
            tmp.write(audio.file.read())
        try:
            result = score_recording(
                tmp.name, reference, provider=cfg["provider"], options=cfg["options"]
            )
        except (ValueError, RuntimeError) as e:
            raise HTTPException(500, str(e))
        return result.model_dump()
    finally:
        Path(tmp.name).unlink(missing_ok=True)


@app.get("/api/admin/scoring")
def admin_scoring_get():
    cfg = scoring_config()
    return {
        "provider": cfg["provider"],
        "options": cfg["options"],
        "providers": available_providers(),
    }


@app.put("/api/admin/scoring")
def admin_scoring_put(body: ScoringConfigIn):
    if body.provider not in available_providers():
        raise HTTPException(422, f"未知评分 provider: {body.provider}")
    DATA_DIR.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=DATA_DIR, delete=False
    ) as f:
        json.dump(
            {"provider": body.provider, "options": body.options},
            f,
            ensure_ascii=False,
        )
    os.replace(f.name, SCORING_PATH)
    return {"provider": body.provider, "options": body.options}


@app.get("/{full_path:path}")
def spa(full_path: str):
    # SPA 路由：dist 存在时托管前端，未知路径回落 index.html
    if full_path.startswith("api/"):
        raise HTTPException(404, "Not Found")
    if DIST.exists():
        candidate = (DIST / full_path).resolve()
        if full_path and str(candidate).startswith(str(DIST.resolve())) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
    return {"status": "frontend not built yet"}


if __name__ == "__main__":
    init_db()
    if os.environ.get("ENLEARN_NO_BROWSER") != "1":
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8420")).start()
    uvicorn.run(app, host="127.0.0.1", port=8420)
