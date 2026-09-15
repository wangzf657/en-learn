"""一次性冒烟测试：起服务、全 API 验证、清理。运行：.venv\\Scripts\\python.exe backend\\smoke_test.py"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
import urllib.error
from contextlib import closing
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "http://127.0.0.1:8420"
FAKE_MP4 = DATA / "test.mp4"
SCORING = DATA / "scoring.json"


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
    # 清掉上次可能的残留
    for f in (DATA / "enlearn.db", FAKE_MP4):
        f.unlink(missing_ok=True)
    FAKE_MP4.write_bytes(os.urandom(1024 * 1024))
    scoring_backup = SCORING.read_bytes() if SCORING.exists() else None
    IMP_DIR = DATA / "import_src"

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

        date = "2026-09-14"
        sub = {"sentences": [
            {"start": 0.0, "end": 2.0, "en": "Hello world.", "zh": "你好，世界。",
             "words": [{"w": "world", "phonetic": "wɜːrld", "note": "n. 世界"}]},
            {"start": 2.0, "end": 4.5, "en": "How are you?"},
        ]}

        # 手动增改端点已移除,直接 sqlite 造数(视频指向 FAKE_MP4 供流测试)
        with closing(sqlite3.connect(DATA / "enlearn.db")) as conn, conn:
            cur = conn.execute(
                "INSERT INTO videos(date, title, video_path, subtitle_json) VALUES (?, ?, ?, ?)",
                (date, "Test EP1", str(FAKE_MP4), json.dumps(sub)),
            )
            vid = cur.lastrowid or 0
        check("sqlite 造数", isinstance(vid, int) and vid > 0, vid)

        s, b, h = req("GET", f"/api/videos/{vid}/stream", headers={"Range": "bytes=0-1023"})
        has_cr = any(k.lower() == "content-range" for k in h)
        check("Range 206", s == 206 and has_cr and len(b) == 1024,
              f"status={s} cr={has_cr} len={len(b)}")
        s, b, h = req("GET", f"/api/videos/{vid}/stream")
        check("无 Range 200 全量", s == 200 and len(b) == 1024 * 1024, f"status={s} len={len(b)}")

        s, b, _ = req("GET", f"/api/day/{date}")
        d = json.loads(b)
        check("get day", s == 200 and d["videoUrl"].endswith(f"/{vid}/stream")
              and len(d["subtitle"]["sentences"]) == 2 and d["checked"] is False, b[:80])
        s, b, _ = req("GET", "/api/day/2026-09-20")
        check("无任务 404", s == 404, b[:60])

        s, b, _ = req("GET", "/api/calendar?month=2026-09")
        d = json.loads(b)
        check("calendar 未打卡", s == 200 and d["days"][0]["checked"] is False, b[:80])

        s, b, _ = req("POST", f"/api/day/{date}/checkin")
        check("checkin 1", s == 200 and json.loads(b) == {"ok": True}, b[:40])
        s, b, _ = req("POST", f"/api/day/{date}/checkin")
        check("checkin 幂等", s == 200 and json.loads(b) == {"ok": True}, b[:40])
        s, b, _ = req("GET", "/api/calendar?month=2026-09")
        check("calendar 已打卡", json.loads(b)["days"][0]["checked"] is True, b[:80])

        s, b, _ = req("GET", "/api/admin/videos")
        d = json.loads(b)["videos"][0]
        check("admin list", d["title"] == "Test EP1" and d["sentenceCount"] == 2
              and d["checked"] is True, b[:100])

        s, b, _ = req("GET", "/", headers={})  # dist 存在 → 返回 index.html
        check("SPA 托管 dist", s == 200 and b"<!doctype html" in b.lower()[:100], f"status={s}")
        s, b, _ = req("GET", "/play/2026-09-14")
        check("SPA fallback", s == 200 and b"<!doctype html" in b.lower()[:100], f"status={s}")

        s, b, _ = req("DELETE", f"/api/admin/videos/{vid}")
        check("DELETE", s == 200, b[:40])
        s, b, _ = req("GET", "/api/admin/videos")
        check("删除后空列表", json.loads(b) == {"videos": []}, b[:40])
        s, b, _ = req("GET", f"/api/day/{date}")
        check("删除后 404", s == 404, b[:40])

        # --- 发音评分(echoic 接入) ---
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

        # --- 按月批量导入视频(覆盖语义) ---
        IMP_DIR.mkdir(exist_ok=True)
        (IMP_DIR / "01_a.mp4").write_bytes(b"")
        (IMP_DIR / "02_b.mp4").write_bytes(b"")
        (IMP_DIR / "02_b.json").write_text(
            json.dumps({"sentences": [{"start": 0.0, "end": 1.0, "en": "Hi."}]}),
            encoding="utf-8")
        (IMP_DIR / "03_d.mp4").write_bytes(b"")
        (IMP_DIR / "03_d.json").write_text("{bad json", encoding="utf-8")
        (IMP_DIR / "32_c.mp4").write_bytes(b"")  # 2026-02 只有 28 天
        (IMP_DIR / "badname.mp4").write_bytes(b"")
        (IMP_DIR / "notes.txt").write_text("x", encoding="utf-8")

        s, b, _ = req("POST", "/api/admin/videos/import",
                      {"path": str(IMP_DIR), "month": "2026-02"})
        d = json.loads(b)
        check("import 首次 updated=false", s == 200
              and [v["date"] for v in d["imported"]] == ["2026-02-01", "2026-02-02"]
              and [v["title"] for v in d["imported"]] == ["a", "b"]
              and all(v["updated"] is False for v in d["imported"]), b[:200])
        check("import skipped 原因", s == 200
              and [x["file"] for x in d["skipped"]] == ["03_d.mp4", "32_c.mp4"]
              and [x["reason"] for x in d["skipped"]] == ["字幕 JSON 无效", "序号超出当月天数"],
              b[:150])
        id_a, id_b = d["imported"][0]["id"], d["imported"][1]["id"]
        s, b, _ = req("GET", "/api/day/2026-02-02")
        d = json.loads(b)
        check("import 字幕自动读入", s == 200 and len(d["subtitle"]["sentences"]) == 1, b[:100])
        s, b, _ = req("POST", "/api/day/2026-02-02/checkin")
        check("import 后 checkin", s == 200, b[:40])

        # 改标题(01_a → 01_aa)与字幕(02_b.json 加一句)后重新导入
        (IMP_DIR / "01_a.mp4").rename(IMP_DIR / "01_aa.mp4")
        (IMP_DIR / "02_b.json").write_text(
            json.dumps({"sentences": [
                {"start": 0.0, "end": 1.0, "en": "Hi."},
                {"start": 1.0, "end": 2.0, "en": "Bye."},
            ]}), encoding="utf-8")

        s, b, _ = req("POST", "/api/admin/videos/import",
                      {"path": str(IMP_DIR), "month": "2026-02"})
        d = json.loads(b)
        check("import 重导 updated=true 且 id 不变", s == 200
              and [v["id"] for v in d["imported"]] == [id_a, id_b]
              and [v["title"] for v in d["imported"]] == ["aa", "b"]
              and all(v["updated"] is True for v in d["imported"]), b[:200])
        s, b, _ = req("GET", "/api/day/2026-02-02")
        d = json.loads(b)
        check("import 覆盖后字幕/打卡保留", s == 200 and d["videoId"] == id_b
              and len(d["subtitle"]["sentences"]) == 2 and d["checked"] is True, b[:120])

        s, b, _ = req("POST", "/api/admin/videos/import",
                      {"path": str(IMP_DIR), "month": "2026-13"})
        check("import month 非法 422", s == 422, b[:60])
        s, b, _ = req("POST", "/api/admin/videos/import",
                      {"path": "X:\\nope_dir", "month": "2026-02"})
        check("import path 不存在 422", s == 422, b[:60])

        fails = [n for n, ok, _ in results if not ok]
        print(f"\n{len(results) - len(fails)}/{len(results)} passed")
        sys.exit(1 if fails else 0)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        for f in (DATA / "enlearn.db", FAKE_MP4):
            f.unlink(missing_ok=True)
        shutil.rmtree(IMP_DIR, ignore_errors=True)
        if scoring_backup is None:
            SCORING.unlink(missing_ok=True)
        else:
            SCORING.write_bytes(scoring_backup)


if __name__ == "__main__":
    main()
