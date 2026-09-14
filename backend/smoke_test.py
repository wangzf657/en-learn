"""一次性冒烟测试：起服务、全 API 验证、清理。运行：.venv\\Scripts\\python.exe backend\\smoke_test.py"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "http://127.0.0.1:8420"
FAKE_MP4 = DATA / "test.mp4"


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


results = []


def check(name: str, ok: bool, detail: object = ""):
    if not isinstance(detail, str):
        detail = detail.decode(errors="replace") if isinstance(detail, bytes) else str(detail)
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def main():
    DATA.mkdir(exist_ok=True)
    # 清掉上次可能的残留
    for f in (DATA / "enlearn.db", FAKE_MP4):
        f.unlink(missing_ok=True)
    FAKE_MP4.write_bytes(os.urandom(1024 * 1024))

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

        s, b, _ = req("POST", "/api/admin/validate-path", {"path": str(FAKE_MP4)})
        check("validate-path 存在", s == 200 and json.loads(b)["exists"] is True, b[:60])
        s, b, _ = req("POST", "/api/admin/validate-path", {"path": "X:\\nope.mp4"})
        check("validate-path 不存在", s == 200 and json.loads(b)["exists"] is False, b[:60])

        s, b, _ = req("POST", "/api/admin/videos",
                      {"date": date, "title": "Test EP1", "videoPath": str(FAKE_MP4),
                       "subtitleJson": json.dumps(sub)})
        check("create 201", s == 201, b[:60])
        vid = json.loads(b)["id"]

        s, b, _ = req("POST", "/api/admin/videos",
                      {"date": date, "title": "dup", "videoPath": "x", "subtitleJson": "{}"})
        check("重复日期 409", s == 409, b[:60])

        s, b, _ = req("POST", "/api/admin/videos",
                      {"date": "2026-09-15", "title": "bad", "videoPath": "x",
                       "subtitleJson": {"nope": 1}})
        check("非法字幕 422", s == 422, b[:60])

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

        s, b, _ = req("PUT", f"/api/admin/videos/{vid}", {"title": "Renamed"})
        check("PUT title", s == 200 and json.loads(b) == {"ok": True}, b[:40])
        s, b, _ = req("GET", "/api/admin/videos")
        d = json.loads(b)["videos"][0]
        check("admin list", d["title"] == "Renamed" and d["sentenceCount"] == 2
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


if __name__ == "__main__":
    main()
