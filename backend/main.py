import json
import os
import re
import sqlite3
import threading
import webbrowser
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "enlearn.db"
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


class VideoCreate(BaseModel):
    date: str
    title: str
    videoPath: str
    subtitleJson: Union[str, dict, None] = None


class VideoUpdate(BaseModel):
    date: Optional[str] = None
    title: Optional[str] = None
    videoPath: Optional[str] = None
    subtitleJson: Union[str, dict, None] = None


class PathIn(BaseModel):
    path: str


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


@app.post("/api/admin/videos", status_code=201)
def admin_create(body: VideoCreate):
    if not valid_date(body.date):
        raise HTTPException(422, "date 格式应为 YYYY-MM-DD")
    with closing(db()) as conn, conn:
        dup = conn.execute("SELECT 1 FROM videos WHERE date = ?", (body.date,)).fetchone()
        if dup:
            raise HTTPException(409, f"日期 {body.date} 已存在视频")
        subtitle = (
            normalize_subtitle(body.subtitleJson)
            if body.subtitleJson is not None
            else '{"sentences":[]}'
        )
        cur = conn.execute(
            "INSERT INTO videos(date, title, video_path, subtitle_json) VALUES (?, ?, ?, ?)",
            (body.date, body.title, body.videoPath, subtitle),
        )
        vid = cur.lastrowid or 0
    return {"id": vid}


@app.put("/api/admin/videos/{vid}")
def admin_update(vid: int, body: VideoUpdate):
    sets, args = [], []
    if body.date is not None:
        if not valid_date(body.date):
            raise HTTPException(422, "date 格式应为 YYYY-MM-DD")
        with closing(db()) as conn, conn:
            dup = conn.execute(
                "SELECT 1 FROM videos WHERE date = ? AND id != ?", (body.date, vid)
            ).fetchone()
        if dup:
            raise HTTPException(409, f"日期 {body.date} 已存在视频")
        sets.append("date = ?")
        args.append(body.date)
    if body.title is not None:
        sets.append("title = ?")
        args.append(body.title)
    if body.videoPath is not None:
        sets.append("video_path = ?")
        args.append(body.videoPath)
    if body.subtitleJson is not None:
        sets.append("subtitle_json = ?")
        args.append(normalize_subtitle(body.subtitleJson))
    if sets:
        args.append(vid)
        with closing(db()) as conn, conn:
            cur = conn.execute(f"UPDATE videos SET {', '.join(sets)} WHERE id = ?", args)
            if cur.rowcount == 0:
                raise HTTPException(404, "视频不存在")
    return {"ok": True}


@app.delete("/api/admin/videos/{vid}")
def admin_delete(vid: int):
    with closing(db()) as conn, conn:
        cur = conn.execute("DELETE FROM videos WHERE id = ?", (vid,))
        if cur.rowcount == 0:
            raise HTTPException(404, "视频不存在")
        conn.execute("DELETE FROM checkins WHERE video_id = ?", (vid,))
    return {"ok": True}


@app.post("/api/admin/validate-path")
def validate_path(body: PathIn):
    p = Path(body.path)
    if p.is_file():
        return {"exists": True, "size": p.stat().st_size}
    return {"exists": False}


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
