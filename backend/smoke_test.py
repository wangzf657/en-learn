"""一次性冒烟测试:起服务、全 API 验证、清理。运行:.venv\\Scripts\\python.exe backend\\smoke_test.py"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from contextlib import closing
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "http://127.0.0.1:8420"
SCORING = DATA / "scoring.json"
LIBRARY = DATA / "library.json"
SRC = DATA / "wow_s1"
SRC2 = DATA / "course_b"
SRC3 = DATA / "vanish"


def req(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    try:
        with urllib.request.urlopen(r) as res:
            return res.status, res.read(), dict(res.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def multipart(path, fields, filename, filedata):
    """multipart/form-data 上传,file 字段固定叫 audio。"""
    boundary = "----smoke" + str(time.time_ns())
    body = b""
    for k, v in fields.items():
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n'
            f"{v}\r\n"
        ).encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; '
        f'filename="{filename}"\r\nContent-Type: audio/wav\r\n\r\n'
    ).encode()
    body += filedata + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    r = urllib.request.Request(BASE + path, data=body, method="POST")
    r.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(r) as res:
            return res.status, res.read(), dict(res.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def wav_bytes(n=1000):
    """最小合法 WAV:44 字节头(16k/16bit/mono)+ 静音数据。"""
    h = bytearray(44)
    h[0:4], h[8:12] = b"RIFF", b"WAVE"
    h[4:8] = (36 + n * 2).to_bytes(4, "little")
    h[12:16], h[16:20] = b"fmt ", (16).to_bytes(4, "little")
    h[20:22], h[22:24] = (1).to_bytes(2, "little"), (1).to_bytes(2, "little")
    h[24:28], h[28:32] = (16000).to_bytes(4, "little"), (32000).to_bytes(4, "little")
    h[32:34], h[34:36] = (2).to_bytes(2, "little"), (16).to_bytes(2, "little")
    h[36:40], h[40:44] = b"data", (n * 2).to_bytes(4, "little")
    return bytes(h) + bytes(n * 2)


def detail(body) -> str:
    try:
        return json.loads(body).get("detail", "")
    except (json.JSONDecodeError, AttributeError):
        return ""


def q(sql, args=()):
    with closing(sqlite3.connect(DATA / "enlearn.db")) as conn:
        return conn.execute(sql, args).fetchall()


def checkin_exists(date: str) -> bool:
    return bool(q("SELECT 1 FROM checkins WHERE date = ?", (date,)))


results = []


def check(name: str, ok: bool, detail: object = ""):
    if not isinstance(detail, str):
        detail = detail.decode(errors="replace") if isinstance(detail, bytes) else str(detail)
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def main():
    # echoic 对接壳自检:纯库调用,不起服务
    from echoic import available_providers, score_recording
    r = score_recording("fake.wav", "Hello world")
    check("echoic provider 注册表", available_providers() == ["mock", "unisound"], str(available_providers()))
    check("echoic mock 评分", r.accuracy_score == 82.5 and len(r.word_scores) == 2,
          r.model_dump_json()[:80])
    try:
        score_recording("x.wav", "y", provider="nope")
        check("echoic 未知 provider 报错", False, "未抛错")
    except ValueError as e:
        check("echoic 未知 provider 报错", "nope" in str(e), str(e)[:60])

    DATA.mkdir(exist_ok=True)
    (DATA / "enlearn.db").unlink(missing_ok=True)
    for d in (SRC, SRC2, SRC3):
        shutil.rmtree(d, ignore_errors=True)
    scoring_backup = SCORING.read_bytes() if SCORING.exists() else None
    library_backup = LIBRARY.read_bytes() if LIBRARY.exists() else None
    LIBRARY.unlink(missing_ok=True)

    # 主课程文件夹:5 有效素材(3.gamma 坏字幕),另有子文件夹与非 mp4
    SRC.mkdir()
    (SRC / "1.alpha.mp4").write_bytes(os.urandom(1024 * 1024))
    (SRC / "1.alpha.srt").write_bytes(
        "\ufeff1\r\n00:00:00,000 --> 00:00:01,000\r\nHello\r\n".encode("utf-8"))
    (SRC / "2.beta.mp4").write_bytes(b"")
    (SRC / "2.beta.json").write_text(
        json.dumps({"sentences": [{"start": 0.0, "end": 1.0, "en": "Hi."}]}), encoding="utf-8")
    (SRC / "3.gamma.mp4").write_bytes(b"")
    (SRC / "3.gamma.json").write_text("{bad json", encoding="utf-8")
    (SRC / "4.delta.mp4").write_bytes(b"")
    (SRC / "5.epsilon.mp4").write_bytes(b"")
    (SRC / "10.omega.mp4").write_bytes(b"")
    (SRC / "notes.txt").write_text("x", encoding="utf-8")
    (SRC / "sub").mkdir()
    (SRC / "sub" / "99.inner.mp4").write_bytes(b"")

    SRC2.mkdir()
    for name in ("1.one.mp4", "2.two.mp4", "3.three.mp4"):
        (SRC2 / name).write_bytes(b"")

    SRC3.mkdir()
    (SRC3 / "1.keep.mp4").write_bytes(b"")
    (SRC3 / "2.gone.mp4").write_bytes(b"")

    env = {**os.environ, "ENLEARN_NO_BROWSER": "1"}
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "backend" / "main.py")], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            time.sleep(0.5)
            try:
                urllib.request.urlopen(BASE + "/api/calendar?month=2026-09", timeout=1)
                break
            except Exception:
                if proc.poll() is not None:
                    print("server died"); sys.exit(1)

        # --- 通用设置:统一前缀 ---
        s, b, _ = req("GET", "/api/admin/library")
        check("library 未配置回落空 root", s == 200 and json.loads(b) == {"root": ""}, b[:80])
        s, b, _ = req("PUT", "/api/admin/library", {"root": str(DATA)})
        check("library PUT", s == 200 and json.loads(b)["root"] == str(DATA), b[:120])
        s, b, _ = req("GET", "/api/admin/library")
        check("library GET 回读", s == 200 and json.loads(b)["root"] == str(DATA), b[:120])
        s, b, _ = req("PUT", "/api/admin/library", {"root": str(DATA / "no_such_root")})
        check("library PUT 非目录 422", s == 422 and detail(b) == "统一前缀目录不存在", b[:100])

        # --- 课程导入 ---
        s, b, _ = req("POST", "/api/admin/courses/import", {"folder": str(SRC)})
        d = json.loads(b)
        course = d["course"]
        titles = [m["title"] for m in d["materials"]]
        check("import 课程已建", s == 200 and course["name"] == "wow_s1" and course["materialCount"] == 5, b[:200])
        check("import 素材自然排序/去前缀", titles == ["alpha", "beta", "delta", "epsilon", "omega"], b[:200])
        check("import 10.omega 排在 4.delta 后", titles.index("delta") < titles.index("omega"), b[:200])
        check("import 子文件夹与非 mp4 忽略", "inner" not in " ".join(titles) and len(titles) == 5, b[:200])
        check("import 首次 updated=false", all(m["updated"] is False for m in d["materials"]), b[:150])
        check("import 坏字幕 skipped", d["skipped"] == [
            {"file": "3.gamma.mp4", "reason": "字幕 JSON 无效"}], b[:150])
        wow_id = course["id"]
        mid = {m["title"]: m["id"] for m in d["materials"]}
        m_alpha, m_beta = mid["alpha"], mid["beta"]
        m_delta, m_epsilon, m_omega = mid["delta"], mid["epsilon"], mid["omega"]

        s, b, _ = req("POST", "/api/admin/courses/import", {"folder": "wow_s1"})
        d = json.loads(b)
        check("相对路径 folder 可导入", s == 200 and d["course"]["materialCount"] == 5, b[:150])
        check("重导幂等 id 稳定/updated=true", {m["title"]: m["id"] for m in d["materials"]} == mid
              and all(m["updated"] is True for m in d["materials"]), b[:200])

        s, b, _ = req("GET", f"/api/admin/courses/{wow_id}")
        d = json.loads(b)
        by_title = {m["title"]: m for m in d["materials"]}
        check("课程详情 字幕入库", s == 200 and by_title["beta"]["sentenceCount"] == 1
              and by_title["alpha"]["sentenceCount"] == 0, b[:200])
        check("课程详情 read/readAt/dates 初始", by_title["alpha"]["read"] is False
              and by_title["alpha"]["readAt"] is None and by_title["alpha"]["dates"] == [], b[:200])

        # --- 库里已有但文件夹里消失的素材保留 ---
        s, b, _ = req("POST", "/api/admin/courses/import", {"folder": "vanish"})
        check("vanish 首次 2 素材", s == 200 and json.loads(b)["course"]["materialCount"] == 2, b[:120])
        (SRC3 / "2.gone.mp4").unlink()
        s, b, _ = req("POST", "/api/admin/courses/import", {"folder": "vanish"})
        d = json.loads(b)
        check("文件消失保留(仍计 2)", s == 200 and len(d["materials"]) == 1
              and d["materials"][0]["updated"] is True and d["course"]["materialCount"] == 2, b[:200])
        s, b, _ = req("GET", "/api/admin/courses")
        vanish = next(c for c in json.loads(b)["courses"] if c["name"] == "vanish")
        s, b, _ = req("GET", f"/api/admin/courses/{vanish['id']}")
        check("消失文件仍在课程详情", s == 200 and len(json.loads(b)["materials"]) == 2, b[:150])

        # --- 前缀边界 ---
        outside = Path(tempfile.mkdtemp())
        (outside / "1.x.mp4").write_bytes(b"")
        try:
            s, b, _ = req("POST", "/api/admin/courses/import", {"folder": str(outside)})
            check("前缀外 422", s == 422 and "之下" in detail(b), b[:150])
        finally:
            shutil.rmtree(outside, ignore_errors=True)
        s, b, _ = req("POST", "/api/admin/courses/import", {"folder": "no_such_folder_xyz"})
        check("文件夹不存在 422", s == 422 and detail(b) == "文件夹不存在", b[:120])

        # --- 排期(打卡管理):均分 / 叠加 / n<d 留空 / 单天 / 跨月 ---
        s, b, _ = req("POST", "/api/admin/schedule",
                      {"courseId": wow_id, "dateFrom": "2026-09-01", "dateTo": "2026-09-04"})
        d = json.loads(b)
        check("schedule 5 素材/4 天 = 2-1-1-1", s == 200 and d["added"] == 5 and d["scheduled"] == [
            {"date": "2026-09-01", "materialIds": [m_alpha, m_beta]},
            {"date": "2026-09-02", "materialIds": [m_delta]},
            {"date": "2026-09-03", "materialIds": [m_epsilon]},
            {"date": "2026-09-04", "materialIds": [m_omega]},
        ], b[:300])
        s, b, _ = req("POST", "/api/admin/schedule",
                      {"courseId": wow_id, "dateFrom": "2026-09-01", "dateTo": "2026-09-04"})
        d = json.loads(b)
        check("schedule 叠加已有 added=0", s == 200 and d["added"] == 0
              and [x["date"] for x in d["scheduled"]] == [
                  "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"], b[:250])

        s, b, _ = req("POST", "/api/admin/courses/import", {"folder": "course_b"})
        d = json.loads(b)
        cb_id = d["course"]["id"]
        cmid = {m["title"]: m["id"] for m in d["materials"]}
        m_one, m_two, m_three = cmid["one"], cmid["two"], cmid["three"]
        check("course_b 导入 3 素材", s == 200 and d["course"]["materialCount"] == 3, b[:150])

        s, b, _ = req("POST", "/api/admin/schedule",
                      {"courseId": cb_id, "dateFrom": "2026-09-10", "dateTo": "2026-09-15"})
        d = json.loads(b)
        check("schedule 3 素材/6 天 = 前 3 天各 1 后 3 天空", s == 200 and d["added"] == 3
              and [x["date"] for x in d["scheduled"]] == ["2026-09-10", "2026-09-11", "2026-09-12"]
              and [x["materialIds"] for x in d["scheduled"]] == [[m_one], [m_two], [m_three]], b[:250])

        s, b, _ = req("POST", "/api/admin/schedule",
                      {"courseId": cb_id, "dateFrom": "2026-09-20", "dateTo": "2026-09-20"})
        d = json.loads(b)
        check("schedule 单天全部素材排到那天", s == 200 and d["added"] == 3 and d["scheduled"] == [
            {"date": "2026-09-20", "materialIds": [m_one, m_two, m_three]}], b[:200])

        s, b, _ = req("POST", "/api/admin/schedule",
                      {"courseId": cb_id, "dateFrom": "2026-09-30", "dateTo": "2026-10-04"})
        d = json.loads(b)
        check("schedule 跨月范围", s == 200 and d["added"] == 3
              and [x["date"] for x in d["scheduled"]] == ["2026-09-30", "2026-10-01", "2026-10-02"],
              b[:250])
        s, b, _ = req("POST", "/api/admin/schedule",
                      {"courseId": 999999, "dateFrom": "2026-09-01", "dateTo": "2026-09-02"})
        check("schedule 课程不存在 404", s == 404 and detail(b) == "课程不存在", b[:80])
        s, b, _ = req("POST", "/api/admin/schedule",
                      {"courseId": wow_id, "dateFrom": "2026-09-05", "dateTo": "2026-09-01"})
        check("schedule 倒序 422", s == 422 and detail(b) == "日期范围无效", b[:80])
        s, b, _ = req("POST", "/api/admin/schedule",
                      {"courseId": wow_id, "dateFrom": "2026/09/01", "dateTo": "2026-09-02"})
        check("schedule 日期格式 422", s == 422 and detail(b) == "日期范围无效", b[:80])

        # --- 课程列表 / 排期视图 ---
        s, b, _ = req("GET", "/api/admin/courses")
        d = json.loads(b)
        names = [c["name"] for c in d["courses"]]
        wow = next(c for c in d["courses"] if c["name"] == "wow_s1")
        check("courses 列表按 name 排序", s == 200 and names == ["course_b", "vanish", "wow_s1"], b[:150])
        check("courses materialCount/readCount/dates", wow["materialCount"] == 5 and wow["readCount"] == 0
              and wow["dates"] == ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"], b[:250])
        s, b, _ = req("GET", "/api/admin/courses/999999")
        check("课程详情 404", s == 404 and detail(b) == "课程不存在", b[:80])

        s, b, _ = req("GET", "/api/admin/schedule?month=2026-09")
        d = json.loads(b)
        days = d["days"]
        check("schedule 月度视图天数", s == 200 and [x["date"] for x in days] == [
            "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-10", "2026-09-11",
            "2026-09-12", "2026-09-20", "2026-09-30"], b[:250])
        check("schedule 月度素材形状", [m["title"] for m in days[0]["materials"]] == ["alpha", "beta"]
              and all(m["courseName"] == "wow_s1" for m in days[0]["materials"])
              and days[4]["materials"][0]["courseName"] == "course_b"
              and days[0]["checked"] is False, b[:250])
        s, b, _ = req("GET", "/api/admin/schedule?month=2026-10")
        check("schedule 跨月落点", s == 200
              and [x["date"] for x in json.loads(b)["days"]] == ["2026-10-01", "2026-10-02"], b[:150])
        s, b, _ = req("GET", "/api/admin/schedule?month=2026-1")
        check("schedule month 格式 422", s == 422, b[:80])

        # --- 消费端 calendar / day / 流 / 字幕 ---
        s, b, _ = req("GET", "/api/calendar?month=2026-09")
        cal = {x["date"]: x for x in json.loads(b)["days"]}
        check("calendar 形状/首素材/count", s == 200 and cal["2026-09-01"]["materialId"] == m_alpha
              and cal["2026-09-01"]["title"] == "alpha" and cal["2026-09-01"]["checked"] is False
              and cal["2026-09-01"]["materialCount"] == 2 and cal["2026-09-20"]["materialCount"] == 3,
              b[:250])

        s, b, _ = req("GET", "/api/day/2026-09-01")
        d = json.loads(b)
        mats = d["materials"]
        check("day 形状/素材排序/字段名", s == 200 and d["date"] == "2026-09-01" and d["checked"] is False
              and [m["id"] for m in mats] == [m_alpha, m_beta]
              and all(m["videoUrl"] == f"/api/materials/{m['id']}/stream" for m in mats), b[:250])
        check("day srtUrl 有无/字幕", mats[0]["srtUrl"] == f"/api/materials/{m_alpha}/srt"
              and mats[1]["srtUrl"] is None and mats[1]["subtitle"]["sentences"][0]["en"] == "Hi."
              and mats[0]["subtitle"]["sentences"] == [], b[:250])
        s, b, _ = req("GET", "/api/day/2026-12-25")
        check("day 无任务 404", s == 404 and detail(b) == "当天没有学习任务", b[:80])
        s, b, _ = req("POST", "/api/day/2026-12-25/checkin")
        check("checkin 无排期 404", s == 404, b[:80])

        s, b, h = req("GET", f"/api/materials/{m_alpha}/stream", headers={"Range": "bytes=0-1023"})
        has_cr = any(k.lower() == "content-range" for k in h)
        check("Range 206", s == 206 and has_cr and len(b) == 1024,
              f"status={s} cr={has_cr} len={len(b)}")
        s, b, _ = req("GET", f"/api/materials/{m_alpha}/stream")
        check("无 Range 200 全量", s == 200 and len(b) == 1024 * 1024, f"status={s} len={len(b)}")
        s, b, h = req("GET", f"/api/materials/{m_alpha}/srt")
        ct = next((v for k, v in h.items() if k.lower() == "content-type"), "")
        check("srt 端点内容(去 BOM)", s == 200 and b.startswith(b"1") and b"Hello" in b
              and "text/plain" in ct, f"status={s} ct={ct} body={b[:40]}")
        s, b, _ = req("GET", f"/api/materials/{m_beta}/srt")
        check("srt 无文件 404", s == 404, b[:60])
        s, b, _ = req("GET", "/api/materials/999999/srt")
        check("srt 素材不存在 404", s == 404, b[:60])

        # --- 打卡置已读 ---
        s, b, _ = req("POST", "/api/day/2026-09-01/checkin")
        check("checkin 首次 ok", s == 200 and json.loads(b) == {"ok": True}, b[:40])
        s, b, _ = req("GET", f"/api/admin/courses/{wow_id}")
        by_title = {m["title"]: m for m in json.loads(b)["materials"]}
        alpha_at = by_title["alpha"]["readAt"]
        check("首次打卡置当天素材已读", by_title["alpha"]["read"] is True and alpha_at
              and by_title["beta"]["read"] is True and "T" in alpha_at, b[:200])
        time.sleep(1.1)
        req("POST", "/api/day/2026-09-01/checkin")
        s, b, _ = req("GET", f"/api/admin/courses/{wow_id}")
        by_title = {m["title"]: m for m in json.loads(b)["materials"]}
        check("重复打卡 readAt 不变", by_title["alpha"]["readAt"] == alpha_at, b[:150])
        s, b, _ = req("GET", "/api/calendar?month=2026-09")
        cal = {x["date"]: x for x in json.loads(b)["days"]}
        check("calendar 已打卡", cal["2026-09-01"]["checked"] is True, b[:120])

        # --- 手动已读切换 ---
        s, b, _ = req("PUT", f"/api/admin/materials/{m_epsilon}/read", {"read": True})
        d = json.loads(b)
        eps_at = d["readAt"]
        check("read=true 置时间", s == 200 and d["read"] is True and eps_at and "T" in eps_at, b[:120])
        time.sleep(1.1)
        s, b, _ = req("PUT", f"/api/admin/materials/{m_epsilon}/read", {"read": True})
        check("已读再 true 时间不变(幂等)", json.loads(b)["readAt"] == eps_at, b[:120])
        s, b, _ = req("PUT", f"/api/admin/materials/{m_epsilon}/read", {"read": False})
        check("read=false 置 NULL", json.loads(b)["read"] is False and json.loads(b)["readAt"] is None, b[:120])
        s, b, _ = req("PUT", "/api/admin/materials/999999/read", {"read": True})
        check("read 素材不存在 404", s == 404 and detail(b) == "素材不存在", b[:80])

        req("PUT", f"/api/admin/materials/{m_epsilon}/read", {"read": True})
        time.sleep(1.1)
        s, b, _ = req("GET", f"/api/admin/courses/{wow_id}")
        eps_before = {m["title"]: m["readAt"] for m in json.loads(b)["materials"]}["epsilon"]
        req("POST", "/api/day/2026-09-03/checkin")
        s, b, _ = req("GET", f"/api/admin/courses/{wow_id}")
        check("手动已读素材打卡后保留原时间",
              {m["title"]: m["readAt"] for m in json.loads(b)["materials"]}["epsilon"] == eps_before,
              b[:200])

        s, b, _ = req("GET", f"/api/admin/courses/{cb_id}")
        one_before = {m["title"]: m for m in json.loads(b)["materials"]}["one"]
        time.sleep(1.1)
        req("POST", "/api/day/2026-09-10/checkin")
        s, b, _ = req("GET", f"/api/admin/courses/{cb_id}")
        one_after = {m["title"]: m for m in json.loads(b)["materials"]}["one"]
        check("打卡给未读素材补已读", one_before["readAt"] is None and one_after["read"] is True
              and one_after["readAt"], b[:200])
        time.sleep(1.1)
        req("POST", "/api/day/2026-09-10/checkin")
        s, b, _ = req("GET", f"/api/admin/courses/{cb_id}")
        check("重复打卡已读时间不变",
              {m["title"]: m["readAt"] for m in json.loads(b)["materials"]}["one"] == one_after["readAt"],
              b[:150])

        # --- 前缀未配置场景 ---
        LIBRARY.unlink(missing_ok=True)
        s, b, _ = req("POST", "/api/admin/courses/import", {"folder": "wow_s1"})
        check("未配置导入 422", s == 422 and detail(b) == "未配置统一前缀", b[:100])
        s, b, _ = req("GET", f"/api/materials/{m_alpha}/stream")
        check("未配置 stream 422", s == 422 and detail(b) == "未配置统一前缀", b[:100])
        s, b, _ = req("GET", f"/api/materials/{m_alpha}/srt")
        check("未配置 srt 422", s == 422, b[:80])
        s, b, _ = req("GET", "/api/day/2026-09-01")
        check("未配置 day srtUrl 置空", s == 200 and json.loads(b)["materials"][0]["srtUrl"] is None, b[:150])
        req("PUT", "/api/admin/library", {"root": str(DATA)})
        s, b, _ = req("GET", "/api/day/2026-09-01")
        check("前缀恢复 srtUrl 回来",
              json.loads(b)["materials"][0]["srtUrl"] == f"/api/materials/{m_alpha}/srt", b[:150])

        # --- 逐天补素材 / 清空当天 / 移除单素材 ---
        s, b, _ = req("POST", "/api/admin/day/2026-09-05/materials", {"materialIds": [m_alpha, m_beta]})
        check("逐天补素材 added 计数", s == 200 and json.loads(b) == {"added": 2}, b[:80])
        s, b, _ = req("POST", "/api/admin/day/2026-09-05/materials", {"materialIds": [m_alpha]})
        check("逐天补素材 叠加 added=0", s == 200 and json.loads(b) == {"added": 0}, b[:80])
        s, b, _ = req("POST", "/api/admin/day/2026-09-05/materials", {"materialIds": [999999]})
        check("补素材未知 id 422", s == 422 and detail(b) == "素材不存在: 999999", b[:100])
        s, b, _ = req("POST", "/api/admin/day/2026-09-05/materials", {"materialIds": []})
        check("补素材空数组 422", s == 422 and detail(b) == "materialIds 不能为空", b[:100])
        s, b, _ = req("POST", "/api/admin/day/2026-9-5/materials", {"materialIds": [m_alpha]})
        check("补素材坏 date 422", s == 422, b[:80])

        req("POST", "/api/day/2026-09-05/checkin")
        s, b, _ = req("DELETE", "/api/admin/day/2026-09-05")
        check("清空当天 removed 计数", s == 200 and json.loads(b) == {"ok": True, "removed": 2}, b[:100])
        s, b, _ = req("GET", "/api/day/2026-09-05")
        check("清空当天后 404", s == 404, b[:80])
        check("清空当天清打卡", not checkin_exists("2026-09-05"), "checkins 不应有 2026-09-05")

        req("POST", "/api/admin/day/2026-09-06/materials", {"materialIds": [m_alpha, m_beta]})
        s, b, _ = req("DELETE", f"/api/admin/day/2026-09-06/materials/{m_beta}")
        check("移除单素材 ok", s == 200 and json.loads(b) == {"ok": True}, b[:60])
        s, b, _ = req("GET", "/api/day/2026-09-06")
        check("移除单素材后当天仍在", s == 200
              and [m["id"] for m in json.loads(b)["materials"]] == [m_alpha], b[:120])
        req("DELETE", "/api/admin/day/2026-09-06")

        s, b, _ = req("DELETE", f"/api/admin/day/2026-09-10/materials/{m_two}")
        check("移除未排素材 422", s == 422 and detail(b) == "当天未排此素材", b[:100])
        s, b, _ = req("DELETE", f"/api/admin/day/2026-09-10/materials/{m_one}")
        check("移除最后一本 ok", s == 200, b[:60])
        s, b, _ = req("GET", "/api/day/2026-09-10")
        check("当天排空后 404", s == 404, b[:80])
        check("当天排空清打卡", not checkin_exists("2026-09-10"), "checkins 不应有 2026-09-10")
        s, b, _ = req("DELETE", f"/api/admin/day/2026-09-10/materials/{m_one}")
        check("无排期移除 404", s == 404 and detail(b) == "当天没有学习任务", b[:100])
        s, b, _ = req("DELETE", f"/api/admin/day/2026-09-02/materials/{m_delta}")
        check("移除单素材清空天", s == 200, b[:60])

        # --- 清空当月 ---
        s, b, _ = req("POST", "/api/admin/schedule",
                      {"courseId": cb_id, "dateFrom": "2026-11-01", "dateTo": "2026-11-03"})
        check("清空当月前置排课", s == 200 and json.loads(b)["added"] == 3, b[:100])
        req("POST", "/api/day/2026-11-01/checkin")
        check("清空当月前打卡存在", checkin_exists("2026-11-01"))
        s, b, _ = req("DELETE", "/api/admin/schedule?month=2026-11")
        check("清空当月 removed 计数", s == 200 and json.loads(b) == {"ok": True, "removed": 3}, b[:100])
        s, b, _ = req("GET", "/api/admin/schedule?month=2026-11")
        check("清空当月后空", s == 200 and json.loads(b)["days"] == [], b[:100])
        check("清空当月清打卡", not checkin_exists("2026-11-01"), "checkins 不应有 2026-11-01")
        s, b, _ = req("DELETE", "/api/admin/schedule?month=2026-1")
        check("清空当月 month 格式 422", s == 422, b[:80])

        # --- 级联删除 ---
        req("POST", "/api/day/2026-10-02/checkin")
        s, b, _ = req("DELETE", f"/api/admin/materials/{m_three}")
        check("删素材级联排班计数", s == 200 and json.loads(b) == {"ok": True, "removedSchedules": 3}, b[:100])
        s, b, _ = req("GET", "/api/calendar?month=2026-10")
        check("删素材后跨月落点消失", s == 200
              and [x["date"] for x in json.loads(b)["days"]] == ["2026-10-01"], b[:150])
        check("删素材清孤儿打卡", not checkin_exists("2026-10-02"), "checkins 不应有 2026-10-02")
        s, b, _ = req("DELETE", "/api/admin/materials/999999")
        check("删素材不存在 404", s == 404 and detail(b) == "素材不存在", b[:80])

        pre_mats = q("SELECT COUNT(*) FROM materials WHERE course_id = ?", (cb_id,))[0][0]
        pre_sched = q("SELECT COUNT(*) FROM day_materials dm JOIN materials m ON m.id = dm.material_id "
                      "WHERE m.course_id = ?", (cb_id,))[0][0]
        s, b, _ = req("DELETE", f"/api/admin/courses/{cb_id}")
        check("删课程级联计数", s == 200 and json.loads(b) == {
            "ok": True, "removedMaterials": pre_mats, "removedSchedules": pre_sched}, b[:150])
        s, b, _ = req("GET", "/api/admin/courses")
        check("删课程后列表消失", s == 200
              and all(c["id"] != cb_id for c in json.loads(b)["courses"]), b[:150])
        s, b, _ = req("GET", "/api/day/2026-09-11")
        check("删课程后排期天 404", s == 404, b[:80])
        s, b, _ = req("DELETE", "/api/admin/courses/999999")
        check("删课程不存在 404", s == 404 and detail(b) == "课程不存在", b[:80])

        s, b, _ = req("GET", "/", headers={})  # dist 存在 → 返回 index.html
        check("SPA 托管 dist", s == 200 and b"<!doctype html" in b.lower()[:100], f"status={s}")
        s, b, _ = req("GET", "/play/2026-09-01")
        check("SPA fallback", s == 200 and b"<!doctype html" in b.lower()[:100], f"status={s}")

        # --- 发音评分(echoic 接入,不动) ---
        s, b, _ = multipart("/api/score", {}, "rec.wav", wav_bytes())
        check("score 缺 reference 422", s == 422, b[:60])
        SCORING.write_text('{"provider": "mock"}', encoding="utf-8")
        s, b, _ = multipart("/api/score", {"reference": "Hello world"}, "rec.wav", wav_bytes())
        d = json.loads(b)
        words = [w["word"] for w in d["word_scores"]]
        check("score mock 200", s == 200 and d["accuracy_score"] == 82.5
              and words == ["Hello", "world"], f"status={s} {b[:100]}")
        s, b, _ = req("GET", "/api/admin/scoring")
        d = json.loads(b)
        check("admin scoring GET", s == 200 and d["provider"] == "mock"
              and "mock" in d["providers"] and d["options"] == {}, b[:100])
        s, b, _ = req("PUT", "/api/admin/scoring",
                      {"provider": "unisound", "options": {"app_key": "test"}})
        d = json.loads(b)
        check("admin scoring PUT", s == 200 and d["provider"] == "unisound"
              and d["options"] == {"app_key": "test"}, b[:100])
        s, b, _ = req("GET", "/api/admin/scoring")
        d = json.loads(b)
        check("admin scoring 回读一致", s == 200 and d["provider"] == "unisound"
              and d["options"] == {"app_key": "test"}, b[:100])
        s, b, _ = req("PUT", "/api/admin/scoring", {"provider": "nope", "options": {}})
        check("admin scoring 未知 provider 422", s == 422, b[:60])

        fails = [n for n, ok, _ in results if not ok]
        print(f"\n{len(results) - len(fails)}/{len(results)} passed")
        sys.exit(1 if fails else 0)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        (DATA / "enlearn.db").unlink(missing_ok=True)
        for d in (SRC, SRC2, SRC3):
            shutil.rmtree(d, ignore_errors=True)
        if scoring_backup is None:
            SCORING.unlink(missing_ok=True)
        else:
            SCORING.write_bytes(scoring_backup)
        if library_backup is None:
            LIBRARY.unlink(missing_ok=True)
        else:
            LIBRARY.write_bytes(library_backup)


if __name__ == "__main__":
    main()
