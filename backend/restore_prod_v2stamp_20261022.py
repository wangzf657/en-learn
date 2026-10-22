"""生产库 v2 戳回退修复(2026-10-22 事故二)。

背景:v2 实验(SCHEMA_VERSION=2, DROP subtitle_json)曾被短暂部署到生产,
库被打上 v2 戳并删列;回退后的 v1 新包启动即报"数据文件比程序新"拒绝启动。
v2 迁移执行前的自动备份 enlearn.db.bak 是完整 v1 库(含全部教学 JSON),
且与当前库在 课程/素材/排期/打卡 上零差异 —— 直接换回即完整恢复。

步骤:断言校验 → 快照当前 v2 库 → bak 覆盖 enlearn.db → 复核。
运行:backend\\.venv\\Scripts\\python.exe backend\\restore_prod_v2stamp_20261022.py
"""
import shutil
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

D = Path(r"D:\data\data")
CUR = D / "enlearn.db"
BAK = D / "enlearn.db.bak"          # v2 迁移前自动备份(v1,含 subtitle_json)
SNAP = D / "enlearn.db.v2-snapshot"  # 本次修复前对当前 v2 库的快照,留档


def rows(db, sql):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [tuple(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def scalar(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


# --- 1. 前置断言:不满足即退出,不动任何文件 ---
assert scalar(CUR, "PRAGMA user_version") == 2, "当前库不是 v2,情况与预期不符"
assert scalar(BAK, "PRAGMA user_version") == 1, "bak 不是 v1"
assert "subtitle_json" not in [r[1] for r in sqlite3.connect(CUR).execute("PRAGMA table_info(materials)")], "当前库竟有 subtitle_json?"
assert scalar(BAK, "SELECT COUNT(*) FROM materials WHERE subtitle_json != '{\"sentences\":[]}'") == 105, "bak 教学 JSON 不满 105"

for sql, label in [
    ("SELECT id,name FROM courses ORDER BY id", "课程一致"),
    ("SELECT id,title,rel_path,read_at FROM materials ORDER BY id", "素材一致"),
    ("SELECT date,material_id FROM day_materials ORDER BY date,material_id", "排期一致"),
    ("SELECT date FROM checkins ORDER BY date", "打卡一致"),
]:
    assert rows(CUR, sql) == rows(BAK, sql), f"{label} 断言失败,中止"
print("断言全过:当前库与 v1 备份除列结构外完全一致")

# --- 2. 快照当前 v2 库,换回 v1 备份 ---
shutil.copy2(CUR, SNAP)
shutil.copy2(BAK, CUR)
print(f"已快照当前库 -> {SNAP.name};已用 v1 备份覆盖 enlearn.db")

# --- 3. 复核 ---
assert scalar(CUR, "PRAGMA user_version") == 1, "回退后版本戳不是 1"
assert scalar(CUR, "SELECT COUNT(*) FROM materials WHERE subtitle_json != '{\"sentences\":[]}'") == 105
counts = {t: scalar(CUR, f"SELECT COUNT(*) FROM {t}") for t in ("courses", "materials", "day_materials", "checkins")}
print(f"复核通过:user_version=1,教学 JSON 105/105,行数 {counts}")
print("完成 —— 现在可正常启动新 exe(v1 程序,零迁移)")
