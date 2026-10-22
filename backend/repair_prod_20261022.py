"""修复 2026-10-22 冒烟测试误打生产库(D:\\data\\data)造成的数据污染。

损害:1) 垃圾课程 wow_s1/vanish 及其 9 月排期/打卡;2) 2026-11 排课被整月清空
(48 条 = Tire Town School 剩余素材 11-01..11-24 每天 2 个);3) library.json/
scoring.json 被覆盖。

运行:backend\\.venv\\Scripts\\python.exe backend\\repair_prod_20261022.py
"""
import json
import re
import shutil
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = Path(r"D:\data\data\enlearn.db")
LIB = Path(r"D:\data\data\library.json")
SCORE = Path(r"D:\data\data\scoring.json")
BAK = DB.with_suffix(".db.repair-bak")


def natural_key(name: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def main():
    shutil.copy2(DB, BAK)
    print(f"已备份: {BAK}")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None  # 手动事务
    cur = conn.cursor()
    cur.execute("BEGIN")

    # ---- 校验(任何一条不过立即回滚退出) ----
    courses = {r["id"]: r["name"] for r in cur.execute("SELECT id, name FROM courses")}
    assert courses.get(7) == "wow_s1" and courses.get(8) == "vanish", courses
    assert courses.get(6) == "01.Tire Town School", courses
    tire = cur.execute("SELECT id, rel_path FROM materials WHERE course_id = 6").fetchall()
    assert len(tire) == 72, f"Tire Town School 应 72 素材,实际 {len(tire)}"
    mats = sorted(tire, key=lambda r: natural_key(r["rel_path"]))

    oct_rows = cur.execute(
        "SELECT dm.date, dm.material_id FROM day_materials dm "
        "JOIN materials m ON m.id = dm.material_id "
        "WHERE m.course_id = 6 ORDER BY dm.date"
    ).fetchall()
    expect = []
    d = date(2026, 10, 20)
    for i in range(12):
        for j in range(2):
            expect.append((d.isoformat(), mats[i * 2 + j]["id"]))
        d += timedelta(days=1)
    got = [(r["date"], r["material_id"]) for r in oct_rows]
    assert got == expect, "10 月排课与自然顺序均分假设不符,中止"

    nov_count = cur.execute(
        "SELECT COUNT(*) FROM day_materials WHERE date LIKE '2026-11%'"
    ).fetchone()[0]
    assert nov_count == 0, f"11 月应已清空,实际 {nov_count} 条"
    scheduled_ids = {r["material_id"] for r in oct_rows}
    rest = [m for m in mats if m["id"] not in scheduled_ids]
    assert len(rest) == 48, f"未排期素材应 48 个,实际 {len(rest)}"

    checkins_before = [r[0] for r in cur.execute("SELECT date FROM checkins ORDER BY date")]

    # ---- 重建 11 月(11-01..11-24 每天 2 个,自然顺序续排) ----
    d = date(2026, 11, 1)
    for i in range(24):
        for j in range(2):
            cur.execute(
                "INSERT INTO day_materials(date, material_id) VALUES (?, ?)",
                (d.isoformat(), rest[i * 2 + j]["id"]),
            )
        d += timedelta(days=1)

    # ---- 删垃圾课程(镜像 admin_course_delete 语义) ----
    junk_mats = [
        r[0]
        for r in cur.execute("SELECT id FROM materials WHERE course_id IN (7, 8)")
    ]
    for mid in junk_mats:
        cur.execute("DELETE FROM day_materials WHERE material_id = ?", (mid,))
    cur.execute("DELETE FROM materials WHERE course_id IN (7, 8)")
    cur.execute("DELETE FROM courses WHERE id IN (7, 8)")
    cur.execute("DELETE FROM checkins WHERE date NOT IN (SELECT DISTINCT date FROM day_materials)")

    # ---- 复核 ----
    months = [
        (r[0], r[1])
        for r in cur.execute(
            "SELECT substr(date,1,7), COUNT(*) FROM day_materials GROUP BY 1 ORDER BY 1"
        )
    ]
    checkins_after = [r[0] for r in cur.execute("SELECT date FROM checkins ORDER BY date")]
    lost = sorted(set(checkins_before) - set(checkins_after))
    courses_after = [r[0] for r in cur.execute("SELECT name FROM courses ORDER BY id")]
    assert months == [("2026-09", 14), ("2026-10", 43), ("2026-11", 48)], months
    assert lost == ["2026-09-01", "2026-09-03"], lost  # 只清了垃圾打卡
    assert courses_after == ["01.第一级 黄色Wow!Yellow", "01.Tire Town School"], courses_after

    cur.execute("COMMIT")
    conn.close()
    print("月度排期:", months)
    print("清理的垃圾打卡:", lost)
    print("课程:", courses_after)

    # ---- 配置恢复 ----
    LIB.write_text(json.dumps({"root": "D:\\data"}, ensure_ascii=False), encoding="utf-8")
    # 原配置的 appkey 已被覆盖丢失,保留非敏感项,AppKey 需在管理页重填
    SCORE.write_text(
        json.dumps(
            {"provider": "unisound", "options": {"mode": "E", "base_url": "http://edu.hivoice.cn/eval"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print("library.json -> D:\\data (媒体库根,按盘上课程文件夹证据恢复)")
    print("scoring.json -> unisound(E 模式,AppKey 需重填)")


if __name__ == "__main__":
    main()
