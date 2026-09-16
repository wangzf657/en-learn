import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import webbrowser
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from echoic import available_providers, score_recording

if getattr(sys, "frozen", False):
    # PyInstaller 打包:只读资源在解包目录,可写数据放 exe 旁边
    BASE_DIR = Path(sys.executable).resolve().parent
    ASSET_DIR = Path(getattr(sys, "_MEIPASS"))
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    ASSET_DIR = BASE_DIR
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "enlearn.db"
SCORING_PATH = DATA_DIR / "scoring.json"
LIBRARY_PATH = DATA_DIR / "library.json"
DIST = ASSET_DIR / "frontend" / "dist"

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  rel_path TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS materials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  rel_path TEXT NOT NULL UNIQUE,
  subtitle_json TEXT NOT NULL DEFAULT '{"sentences":[]}',
  read_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS day_materials (
  date TEXT NOT NULL,
  material_id INTEGER NOT NULL,
  PRIMARY KEY (date, material_id)
);
CREATE TABLE IF NOT EXISTS checkins (
  date TEXT PRIMARY KEY,
  checked_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

app = FastAPI(title="EnLearn")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


SCHEMA_VERSION = 1
# 结构升级记录:每项 (目标版本, SQL 脚本)。库版本低于目标版本时按序原地执行(原子包在 BEGIN/COMMIT 里),
# 首次执行前自动备份 enlearn.db.bak;数据文件版本比程序新则拒绝启动。
MIGRATIONS = [
    # 示例: (2, "ALTER TABLE materials ADD COLUMN note TEXT;"),
]


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    with closing(db()) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            sys.exit(f"数据文件比程序新(数据 v{version},程序 v{SCHEMA_VERSION}),请使用新版 EnLearn")
        if version == 0:
            # 全新库,或旧版未打版本戳的库:SCHEMA 全是 IF NOT EXISTS,补跑无副作用
            conn.executescript(SCHEMA)
            # 旧「书籍库」模型已废弃,数据为空,直接换表不迁移
            conn.execute("DROP TABLE IF EXISTS day_books")
            conn.execute("DROP TABLE IF EXISTS books")
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.commit()
            return
        pending = [(v, sql) for v, sql in MIGRATIONS if v > version]
        if not pending:
            return
        shutil.copy2(DB_PATH, DATA_DIR / "enlearn.db.bak")
        for to_ver, sql in pending:
            conn.executescript(f"BEGIN;{sql}\nPRAGMA user_version = {to_ver};COMMIT;")


def library_config() -> dict:
    """读统一前缀配置;文件缺失/损坏时回落空 root。每次请求现读,改配置即时生效。"""
    try:
        with open(LIBRARY_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"root": ""}
    if not isinstance(cfg, dict):
        return {"root": ""}
    return {"root": cfg.get("root") or ""}


def resolve_import_folder(folder: str):
    """解析导入文件夹:(绝对目录, 相对 root 前缀, root 字符串)。不合法抛 422。"""
    root = library_config()["root"]
    if not root:
        raise HTTPException(422, "未配置统一前缀")
    root_dir = Path(root).resolve()
    p = Path(folder)
    candidate = (p if p.is_absolute() else root_dir / folder).resolve()
    if not candidate.is_dir():
        raise HTTPException(422, "文件夹不存在")
    if candidate != root_dir and root_dir not in candidate.parents:
        raise HTTPException(422, f"导入文件夹必须在统一前缀 {root} 之下")
    rel = candidate.relative_to(root_dir).as_posix()
    return candidate, ("" if rel == "." else rel), root


def natural_key(name: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def material_key(row):
    return natural_key(Path(row["rel_path"]).name)


def clean_orphan_checkins(conn):
    """删掉的排期若让某天变空,连当天的打卡一起清掉。"""
    conn.execute(
        "DELETE FROM checkins WHERE date NOT IN (SELECT DISTINCT date FROM day_materials)"
    )


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


# ---------------------------------------------------------------- 消费端

@app.get("/api/calendar")
def calendar(month: str):
    if not re.fullmatch(r"\d{4}-\d{2}", month or ""):
        raise HTTPException(422, "month 格式应为 YYYY-MM")
    with closing(db()) as conn, conn:
        rows = conn.execute(
            "SELECT m.id, dm.date, m.title, m.rel_path, ck.date AS checked_date "
            "FROM day_materials dm JOIN materials m ON m.id = dm.material_id "
            "LEFT JOIN checkins ck ON ck.date = dm.date "
            "WHERE dm.date LIKE ?",
            (month + "-%",),
        ).fetchall()
    groups = {}
    for r in rows:
        groups.setdefault(r["date"], []).append(r)
    days = []
    for date in sorted(groups):
        rs = sorted(groups[date], key=material_key)
        days.append(
            {
                "date": date,
                "materialId": rs[0]["id"],
                "title": rs[0]["title"],
                "checked": rs[0]["checked_date"] is not None,
                "materialCount": len(rs),
            }
        )
    return {"days": days}


@app.get("/api/day/{date}")
def get_day(date: str):
    if not valid_date(date):
        raise HTTPException(422, "date 格式应为 YYYY-MM-DD")
    with closing(db()) as conn, conn:
        rows = conn.execute(
            "SELECT m.* FROM day_materials dm JOIN materials m ON m.id = dm.material_id "
            "WHERE dm.date = ?",
            (date,),
        ).fetchall()
        if not rows:
            raise HTTPException(404, "当天没有学习任务")
        checked = (
            conn.execute("SELECT 1 FROM checkins WHERE date = ?", (date,)).fetchone()
            is not None
        )
    root = library_config()["root"]
    materials = []
    for r in sorted(rows, key=material_key):
        has_srt = bool(root) and (Path(root) / r["rel_path"]).with_suffix(".srt").is_file()
        materials.append(
            {
                "id": r["id"],
                "title": r["title"],
                "videoUrl": f"/api/materials/{r['id']}/stream",
                "srtUrl": f"/api/materials/{r['id']}/srt" if has_srt else None,
                "subtitle": json.loads(r["subtitle_json"]),
            }
        )
    return {"date": date, "checked": checked, "materials": materials}


@app.post("/api/day/{date}/checkin")
def checkin(date: str):
    if not valid_date(date):
        raise HTTPException(422, "date 格式应为 YYYY-MM-DD")
    with closing(db()) as conn, conn:
        rows = conn.execute(
            "SELECT material_id FROM day_materials WHERE date = ?", (date,)
        ).fetchall()
        if not rows:
            raise HTTPException(404, "当天没有学习任务")
        inserted = conn.execute(
            "INSERT OR IGNORE INTO checkins(date) VALUES (?)", (date,)
        ).rowcount
        if inserted:
            # 首次打卡:当天素材标已读;手动已读的保留原时间
            conn.execute(
                "UPDATE materials SET read_at = ? WHERE read_at IS NULL AND id IN "
                "(SELECT material_id FROM day_materials WHERE date = ?)",
                (now_iso(), date),
            )
    return {"ok": True}


@app.get("/api/materials/{mid}/stream")
def stream(mid: int):
    root = library_config()["root"]
    if not root:
        raise HTTPException(422, "未配置统一前缀")
    with closing(db()) as conn, conn:
        r = conn.execute("SELECT rel_path FROM materials WHERE id = ?", (mid,)).fetchone()
    if not r:
        raise HTTPException(404, "素材不存在")
    path = Path(root) / r["rel_path"]
    if not path.is_file():
        raise HTTPException(404, f"文件不存在: {path}")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/materials/{mid}/srt")
def srt(mid: int):
    root = library_config()["root"]
    if not root:
        raise HTTPException(422, "未配置统一前缀")
    with closing(db()) as conn, conn:
        r = conn.execute("SELECT rel_path FROM materials WHERE id = ?", (mid,)).fetchone()
    if not r:
        raise HTTPException(404, "素材不存在")
    path = (Path(root) / r["rel_path"]).with_suffix(".srt")
    if not path.is_file():
        raise HTTPException(404, "字幕文件不存在")
    return PlainTextResponse(
        path.read_text(encoding="utf-8-sig"),
        media_type="text/plain; charset=utf-8",
    )


# ---------------------------------------------------------------- 通用设置

class ScoringConfigIn(BaseModel):
    provider: str
    options: dict = {}


class LibraryIn(BaseModel):
    root: str


class CourseImportIn(BaseModel):
    folder: str


class ScheduleIn(BaseModel):
    courseId: int
    dateFrom: str
    dateTo: str


class MaterialIdsIn(BaseModel):
    materialIds: list[int]


class ReadIn(BaseModel):
    read: bool


@app.get("/api/admin/library")
def admin_library_get():
    return {"root": library_config()["root"]}


@app.put("/api/admin/library")
def admin_library_put(body: LibraryIn):
    if not Path(body.root).is_dir():
        raise HTTPException(422, "统一前缀目录不存在")
    DATA_DIR.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=DATA_DIR, delete=False
    ) as f:
        json.dump({"root": body.root}, f, ensure_ascii=False)
    os.replace(f.name, LIBRARY_PATH)
    return {"root": body.root}


# ---------------------------------------------------------------- 课程管理

@app.post("/api/admin/courses/import")
def admin_courses_import(body: CourseImportIn):
    folder, prefix, _root = resolve_import_folder(body.folder)
    files = sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".mp4"),
        key=lambda p: natural_key(p.name),
    )
    valid, skipped = [], []
    for f in files:
        subtitle = '{"sentences":[]}'
        sub_file = f.with_suffix(".json")
        if sub_file.is_file():
            try:
                subtitle = normalize_subtitle(sub_file.read_text(encoding="utf-8"))
            except (HTTPException, OSError, UnicodeDecodeError):
                skipped.append({"file": f.name, "reason": "字幕 JSON 无效"})
                continue
        valid.append((f, re.sub(r"^\d{1,3}[._-]\s*", "", f.stem), subtitle))

    name = folder.name or str(folder)
    with closing(db()) as conn, conn:
        row = conn.execute("SELECT id FROM courses WHERE rel_path = ?", (prefix,)).fetchone()
        if row:
            course_id = row["id"]
            conn.execute("UPDATE courses SET name = ? WHERE id = ?", (name, course_id))
        else:
            course_id = conn.execute(
                "INSERT INTO courses(name, rel_path) VALUES (?, ?)", (name, prefix)
            ).lastrowid
        materials = []
        for f, title, subtitle in valid:
            rel_path = f"{prefix}/{f.name}" if prefix else f.name
            m = conn.execute(
                "SELECT id FROM materials WHERE rel_path = ?", (rel_path,)
            ).fetchone()
            if m:
                mid, updated = m["id"], True
                conn.execute(
                    "UPDATE materials SET course_id = ?, title = ?, subtitle_json = ? "
                    "WHERE id = ?",
                    (course_id, title, subtitle, mid),
                )
            else:
                mid = conn.execute(
                    "INSERT INTO materials(course_id, title, rel_path, subtitle_json) "
                    "VALUES (?, ?, ?, ?)",
                    (course_id, title, rel_path, subtitle),
                ).lastrowid
                updated = False
            materials.append({"id": mid, "title": title, "updated": updated})
        material_count = conn.execute(
            "SELECT COUNT(*) FROM materials WHERE course_id = ?", (course_id,)
        ).fetchone()[0]
    return {
        "course": {"id": course_id, "name": name, "materialCount": material_count},
        "materials": materials,
        "skipped": skipped,
    }


@app.get("/api/admin/courses")
def admin_courses_list():
    with closing(db()) as conn, conn:
        rows = conn.execute("SELECT * FROM courses ORDER BY name").fetchall()
        counts = {
            r["course_id"]: r
            for r in conn.execute(
                "SELECT course_id, COUNT(*) AS total, "
                "SUM(CASE WHEN read_at IS NOT NULL THEN 1 ELSE 0 END) AS read_n "
                "FROM materials GROUP BY course_id"
            )
        }
        dates_map = {}
        for r in conn.execute(
            "SELECT m.course_id, dm.date FROM day_materials dm "
            "JOIN materials m ON m.id = dm.material_id ORDER BY dm.date"
        ):
            dates_map.setdefault(r["course_id"], set()).add(r["date"])
    courses = []
    for r in rows:
        c = counts.get(r["id"])
        courses.append(
            {
                "id": r["id"],
                "name": r["name"],
                "materialCount": c["total"] if c else 0,
                "readCount": (c["read_n"] or 0) if c else 0,
                "dates": sorted(dates_map.get(r["id"], set())),
            }
        )
    return {"courses": courses}


@app.get("/api/admin/courses/{cid}")
def admin_course_detail(cid: int):
    with closing(db()) as conn, conn:
        c = conn.execute("SELECT * FROM courses WHERE id = ?", (cid,)).fetchone()
        if not c:
            raise HTTPException(404, "课程不存在")
        rows = conn.execute(
            "SELECT * FROM materials WHERE course_id = ?", (cid,)
        ).fetchall()
        dates_map = {}
        for r in conn.execute(
            "SELECT dm.material_id, dm.date FROM day_materials dm "
            "JOIN materials m ON m.id = dm.material_id WHERE m.course_id = ? "
            "ORDER BY dm.date",
            (cid,),
        ):
            dates_map.setdefault(r["material_id"], []).append(r["date"])
    materials = []
    for r in sorted(rows, key=material_key):
        try:
            subtitle = json.loads(r["subtitle_json"])
        except (json.JSONDecodeError, AttributeError):
            subtitle = {"sentences": []}
        n = len(subtitle.get("sentences", []))
        materials.append(
            {
                "id": r["id"],
                "title": r["title"],
                "relPath": r["rel_path"],
                "sentenceCount": n,
                "read": r["read_at"] is not None,
                "readAt": r["read_at"],
                "dates": dates_map.get(r["id"], []),
                "subtitle": subtitle,
            }
        )
    return {"id": c["id"], "name": c["name"], "materials": materials}


@app.delete("/api/admin/courses/{cid}")
def admin_course_delete(cid: int):
    with closing(db()) as conn, conn:
        if not conn.execute("SELECT 1 FROM courses WHERE id = ?", (cid,)).fetchone():
            raise HTTPException(404, "课程不存在")
        mids = [
            r["id"]
            for r in conn.execute("SELECT id FROM materials WHERE course_id = ?", (cid,))
        ]
        removed_schedules = 0
        for mid in mids:
            removed_schedules += conn.execute(
                "DELETE FROM day_materials WHERE material_id = ?", (mid,)
            ).rowcount
        conn.execute("DELETE FROM materials WHERE course_id = ?", (cid,))
        conn.execute("DELETE FROM courses WHERE id = ?", (cid,))
        clean_orphan_checkins(conn)
    return {
        "ok": True,
        "removedMaterials": len(mids),
        "removedSchedules": removed_schedules,
    }


@app.delete("/api/admin/materials/{mid}")
def admin_material_delete(mid: int):
    with closing(db()) as conn, conn:
        if not conn.execute("SELECT 1 FROM materials WHERE id = ?", (mid,)).fetchone():
            raise HTTPException(404, "素材不存在")
        removed = conn.execute(
            "DELETE FROM day_materials WHERE material_id = ?", (mid,)
        ).rowcount
        conn.execute("DELETE FROM materials WHERE id = ?", (mid,))
        clean_orphan_checkins(conn)
    return {"ok": True, "removedSchedules": removed}


@app.put("/api/admin/materials/{mid}/read")
def admin_material_read(mid: int, body: ReadIn):
    with closing(db()) as conn, conn:
        r = conn.execute("SELECT read_at FROM materials WHERE id = ?", (mid,)).fetchone()
        if not r:
            raise HTTPException(404, "素材不存在")
        read_at = r["read_at"]
        if body.read:
            if read_at is None:
                read_at = now_iso()
                conn.execute(
                    "UPDATE materials SET read_at = ? WHERE id = ?", (read_at, mid)
                )
        else:
            read_at = None
            conn.execute("UPDATE materials SET read_at = NULL WHERE id = ?", (mid,))
    return {"id": mid, "read": read_at is not None, "readAt": read_at}


# ---------------------------------------------------------------- 排期(打卡管理)

@app.post("/api/admin/schedule")
def admin_schedule(body: ScheduleIn):
    if not valid_date(body.dateFrom) or not valid_date(body.dateTo):
        raise HTTPException(422, "日期范围无效")
    start = datetime.strptime(body.dateFrom, "%Y-%m-%d").date()
    end = datetime.strptime(body.dateTo, "%Y-%m-%d").date()
    if start > end:
        raise HTTPException(422, "日期范围无效")
    days = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    with closing(db()) as conn, conn:
        if not conn.execute(
            "SELECT 1 FROM courses WHERE id = ?", (body.courseId,)
        ).fetchone():
            raise HTTPException(404, "课程不存在")
        rows = conn.execute(
            "SELECT id, rel_path FROM materials WHERE course_id = ?", (body.courseId,)
        ).fetchall()
        mats = sorted(rows, key=material_key)
        n, d = len(mats), len(days)
        if n >= d:
            base, extra = divmod(n, d)
            counts = [base + (1 if k < extra else 0) for k in range(d)]
        else:
            counts = [1 if k < n else 0 for k in range(d)]
        added, idx = 0, 0
        for k, count in enumerate(counts):
            for _ in range(count):
                added += conn.execute(
                    "INSERT OR IGNORE INTO day_materials(date, material_id) VALUES (?, ?)",
                    (days[k], mats[idx]["id"]),
                ).rowcount
                idx += 1
        scheduled = []
        for day in days:
            on_day = conn.execute(
                "SELECT m.id, m.rel_path FROM day_materials dm "
                "JOIN materials m ON m.id = dm.material_id WHERE dm.date = ?",
                (day,),
            ).fetchall()
            if on_day:
                scheduled.append(
                    {
                        "date": day,
                        "materialIds": [r["id"] for r in sorted(on_day, key=material_key)],
                    }
                )
    return {"added": added, "scheduled": scheduled}


@app.get("/api/admin/schedule")
def admin_schedule_get(month: str):
    if not re.fullmatch(r"\d{4}-\d{2}", month or ""):
        raise HTTPException(422, "month 格式应为 YYYY-MM")
    with closing(db()) as conn, conn:
        rows = conn.execute(
            "SELECT dm.date, m.id, m.title, m.rel_path, c.name AS course_name, "
            "ck.date AS checked_date FROM day_materials dm "
            "JOIN materials m ON m.id = dm.material_id "
            "JOIN courses c ON c.id = m.course_id "
            "LEFT JOIN checkins ck ON ck.date = dm.date "
            "WHERE dm.date LIKE ?",
            (month + "-%",),
        ).fetchall()
    groups = {}
    for r in rows:
        groups.setdefault(r["date"], []).append(r)
    days = []
    for date in sorted(groups):
        rs = sorted(groups[date], key=material_key)
        days.append(
            {
                "date": date,
                "checked": rs[0]["checked_date"] is not None,
                "materials": [
                    {"id": r["id"], "title": r["title"], "courseName": r["course_name"]}
                    for r in rs
                ],
            }
        )
    return {"days": days}


@app.delete("/api/admin/schedule")
def admin_schedule_clear(month: str):
    if not re.fullmatch(r"\d{4}-\d{2}", month or ""):
        raise HTTPException(422, "month 格式应为 YYYY-MM")
    with closing(db()) as conn, conn:
        removed = conn.execute(
            "DELETE FROM day_materials WHERE date LIKE ?", (month + "-%",)
        ).rowcount
        conn.execute("DELETE FROM checkins WHERE date LIKE ?", (month + "-%",))
    return {"ok": True, "removed": removed}


@app.post("/api/admin/day/{date}/materials")
def admin_day_assign(date: str, body: MaterialIdsIn):
    if not valid_date(date):
        raise HTTPException(422, "date 格式应为 YYYY-MM-DD")
    if not body.materialIds:
        raise HTTPException(422, "materialIds 不能为空")
    with closing(db()) as conn, conn:
        added = 0
        for mid in body.materialIds:
            if not conn.execute(
                "SELECT 1 FROM materials WHERE id = ?", (mid,)
            ).fetchone():
                raise HTTPException(422, f"素材不存在: {mid}")
            added += conn.execute(
                "INSERT OR IGNORE INTO day_materials(date, material_id) VALUES (?, ?)",
                (date, mid),
            ).rowcount
    return {"added": added}


@app.delete("/api/admin/day/{date}")
def admin_day_delete(date: str):
    if not valid_date(date):
        raise HTTPException(422, "date 格式应为 YYYY-MM-DD")
    with closing(db()) as conn, conn:
        removed = conn.execute(
            "DELETE FROM day_materials WHERE date = ?", (date,)
        ).rowcount
        conn.execute("DELETE FROM checkins WHERE date = ?", (date,))
    return {"ok": True, "removed": removed}


@app.delete("/api/admin/day/{date}/materials/{mid}")
def admin_day_material_delete(date: str, mid: int):
    if not valid_date(date):
        raise HTTPException(422, "date 格式应为 YYYY-MM-DD")
    with closing(db()) as conn, conn:
        if not conn.execute(
            "SELECT 1 FROM day_materials WHERE date = ? LIMIT 1", (date,)
        ).fetchone():
            raise HTTPException(404, "当天没有学习任务")
        removed = conn.execute(
            "DELETE FROM day_materials WHERE date = ? AND material_id = ?", (date, mid)
        ).rowcount
        if removed == 0:
            raise HTTPException(422, "当天未排此素材")
        if not conn.execute(
            "SELECT 1 FROM day_materials WHERE date = ? LIMIT 1", (date,)
        ).fetchone():
            conn.execute("DELETE FROM checkins WHERE date = ?", (date,))
    return {"ok": True}


# ---------------------------------------------------------------- 跟读评分(不动)

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
