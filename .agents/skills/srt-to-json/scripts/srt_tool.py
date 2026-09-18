#!/usr/bin/env python3
"""EnLearn SRT→教学字幕 JSON 的结构层工具与校验器。

结构权威:subtitle.schema.json(本 skill 目录);流程与质量要求:.agents/skills/srt-to-json/SKILL.md。

首要规则:原 SRT 的 cue(时间戳 + 台词)是一等公民。JSON 的 sentences 与清洗后的 cue
逐条一一对应(数量、顺序、start/end、en 文本全一致);禁止合并/拆分/改写。
脚本只做确定性清洗与逐条透传,不做任何重组。

用法:
  python srt_tool.py draft <文件夹 | 单个.srt> [--force]   # SRT → 结构 JSON(1 cue = 1 句)
  python srt_tool.py check <文件夹 | a.srt a.json>         # 契约 + 逐句对齐 + 守恒校验
  python srt_tool.py selftest                              # 内置样例自检
"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)
TAG_RE = re.compile(r"<[^>]+>")
LABEL_RE = re.compile(r"^[A-Z][A-Z' .]{1,20}:\s*")  # 说话人标签 JOHN:
BRACKET_RE = re.compile(r"^\[[^\]]*\]$")  # [music] [laughter] 等注解行

ALIGN_TOL = 1e-6  # 时间戳对齐容差(秒)


def _norm(s: str) -> str:
    """守恒比对:统一撇号、小写、只留字母数字。"""
    return re.sub(r"[^a-z0-9]", "", s.replace("\u2019", "'").lower())


def _sec(h, m, s, ms) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def _clean(lines):
    """逐行清洗 cue 文本:去 HTML 标签、丢 ♪/[注解] 行、去说话人标签、折叠空白。"""
    kept = []
    for ln in lines:
        s = TAG_RE.sub("", ln).strip()
        if not s or s.startswith("\u266a") or BRACKET_RE.match(s):
            continue
        s = LABEL_RE.sub("", s)
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            kept.append(s)
    return " ".join(kept)


def parse_srt(path: Path):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gbk")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if lines and lines[0].isdigit():  # 序号行
            lines = lines[1:]
        if not lines:
            continue
        m = TIME_RE.search(lines[0])
        if not m:
            continue
        body = _clean(lines[1:])
        if body:
            cues.append({
                "start": _sec(m.group(1), m.group(2), m.group(3), m.group(4)),
                "end": _sec(m.group(5), m.group(6), m.group(7), m.group(8)),
                "text": body,
            })
    return cues


def _span_in(tokens, need):
    """need 是否为 tokens 的连续子序列(两侧已统一小写/撇号)。

    单元素 = 单词须精确命中 token;多元素 = 词组须与 en 中一段连续词完全一致。
    """
    return any(tokens[i : i + len(need)] == need for i in range(len(tokens) - len(need) + 1))


def check_pair(srt: Path, js: Path):
    """校验富化后的 JSON。返回 (errors, warnings);errors 非空 = 不可交付。"""
    errs, warns = [], []
    try:
        data = json.loads(js.read_text(encoding="utf-8-sig"))
    except Exception as e:
        return [f"{js.name}: JSON 解析失败: {e}"], []
    if not isinstance(data, dict) or not isinstance(data.get("sentences"), list):
        return [f"{js.name}: 必须是含 sentences 数组的对象"], []
    sents = data["sentences"]
    cues = parse_srt(srt)

    # 首要规则:逐句与原 cue 对齐(数量/时间戳/文本)
    if len(sents) != len(cues):
        errs.append(
            f"{js.name}: 句数 {len(sents)} ≠ 原 SRT cue 数 {len(cues)}(禁止合并/拆分/增删)"
        )

    prev_end, all_en = None, ""
    for i, s in enumerate(sents):
        tag = f"{js.name} 第{i + 1}句"
        if not isinstance(s, dict):
            errs.append(f"{tag}: 不是对象")
            continue
        if (
            not isinstance(s.get("start"), (int, float))
            or not isinstance(s.get("end"), (int, float))
            or not isinstance(s.get("en"), str)
        ):
            errs.append(f"{tag}: start/end 必须数字、en 必须字符串(服务端 422)")
            continue
        en = s["en"]
        all_en += en
        if s["end"] <= s["start"]:
            errs.append(f"{tag}: end 必须大于 start")
        if prev_end is not None and s["start"] < prev_end:
            errs.append(f"{tag}: 与上一句时间重叠或乱序")
        prev_end = s["end"]
        if not en.strip():
            errs.append(f"{tag}: en 为空")
        if en != en.strip():
            errs.append(f"{tag}: en 首尾有空白")
        if TAG_RE.search(en):
            errs.append(f"{tag}: en 残留 HTML 标签")
        if i < len(cues):
            c = cues[i]
            if abs(s["start"] - c["start"]) > ALIGN_TOL or abs(s["end"] - c["end"]) > ALIGN_TOL:
                errs.append(
                    f"{tag}: 时间戳与原 cue 不对齐"
                    f"(原 {c['start']:g}–{c['end']:g},现 {s['start']:g}–{s['end']:g})"
                )
            if en != c["text"]:
                errs.append(f"{tag}: en 与原 cue 文本不一致(原「{c['text'][:60]}」,禁止改写)")
        else:
            errs.append(f"{tag}: 超出原 SRT cue 条数(禁止造句)")
        ws = s.get("words")
        if ws is not None:
            if not isinstance(ws, list):
                errs.append(f"{tag}: words 必须是数组")
            else:
                if len(ws) > 5:
                    warns.append(f"{tag}: words {len(ws)} 个 > 5,建议精简")
                tokens = [t.lower() for t in re.findall(r"[A-Za-z']+", en.replace("\u2019", "'"))]
                for j, w in enumerate(ws):
                    wtag = f"{tag} words[{j}]"
                    if not isinstance(w, dict) or not isinstance(w.get("w"), str) or not w["w"].strip():
                        errs.append(f"{wtag}: 缺 w 或非字符串")
                        continue
                    w_tokens = [t.lower() for t in re.findall(r"[A-Za-z']+", w["w"].replace("\u2019", "'"))]
                    if not w_tokens:
                        errs.append(f"{wtag}: w '{w['w']}' 不含有效词")
                        continue
                    if not _span_in(tokens, w_tokens):
                        errs.append(f"{wtag}: w '{w['w']}' 不是 en 中的表层连续片段(单词/词组须与 en 一致)")
                    ph = w.get("phonetic")
                    if ph is not None and (not isinstance(ph, str) or not ph.strip()):
                        errs.append(f"{wtag}: phonetic 空串(删掉该键)")
                    if isinstance(ph, str) and "/" in ph:
                        errs.append(f"{wtag}: phonetic 含斜杠(前端渲染自加 /…/)")
                    n = w.get("note")
                    if n is not None and (not isinstance(n, str) or not n.strip()):
                        errs.append(f"{wtag}: note 空串(删掉该键)")
        for key in ("zh", "note"):
            v = s.get(key)
            if v is not None and (not isinstance(v, str) or not v.strip()):
                errs.append(f"{tag}: {key} 空串(删掉该键)")

    if _norm(" ".join(c["text"] for c in cues)) != _norm(all_en):
        errs.append(f"{js.name}: 文本守恒失败——en 与 SRT 不一致(丢句/造句/改写)")
    return errs, warns


def cmd_draft(args):
    src = Path(args.path)
    srts = sorted(src.rglob("*.srt")) if src.is_dir() else [src]
    if not srts or not all(p.is_file() for p in srts):
        sys.exit(f"ERROR 找不到 SRT: {args.path}")
    for srt in srts:
        out = srt.with_suffix(".json")
        if out.exists() and not args.force:
            print(f"SKIP {out.name}(已存在,--force 覆盖)")
            continue
        cues = parse_srt(srt)
        sents = [{"start": c["start"], "end": c["end"], "en": c["text"]} for c in cues]
        out.write_text(
            json.dumps({"sentences": sents}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"DRAFT {out.name}: {len(sents)} 句(1:1 对应 {len(cues)} 个 cue)")


def cmd_check(args):
    paths = [Path(p) for p in args.paths]
    if len(paths) == 1 and paths[0].is_dir():
        pairs = []
        for srt in sorted(paths[0].rglob("*.srt")):
            js = srt.with_suffix(".json")
            if js.exists():
                pairs.append((srt, js))
            else:
                print(f"MISS {srt.name}: 同名 .json 不存在(未转换?)")
    elif len(paths) == 2 and paths[0].suffix == ".srt" and paths[1].suffix == ".json":
        pairs = [(paths[0], paths[1])]
    else:
        sys.exit("ERROR 用法:check <文件夹> 或 check <文件.srt> <文件.json>")
    failed = False
    for srt, js in pairs:
        errs, warns = check_pair(srt, js)
        for w in warns:
            print(f"WARN {w}")
        if errs:
            failed = True
            for e in errs:
                print(f"ERROR {e}")
        else:
            print(f"OK {js.name}")
    sys.exit(1 if failed else 0)


SAMPLE_SRT = """1
00:00:01,200 --> 00:00:02,100
<i>How you</i>

2
00:00:02,300 --> 00:00:04,500
doing?

3
00:00:05,000 --> 00:00:06,000
♪ Peppa Pig ♪

4
00:00:06,100 --> 00:00:07,900
what is this
"""


def cmd_selftest(args):
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        srt = d / "01_测试.srt"
        srt.write_bytes(b"\xef\xbb\xbf" + SAMPLE_SRT.encode("utf-8"))  # 带 BOM 验证解码
        cues = parse_srt(srt)
        assert len(cues) == 3, cues  # ♪ 音乐行被清洗丢弃
        sents = [{"start": c["start"], "end": c["end"], "en": c["text"]} for c in cues]
        assert sents == [
            {"start": 1.2, "end": 2.1, "en": "How you"},
            {"start": 2.3, "end": 4.5, "en": "doing?"},
            {"start": 6.1, "end": 7.9, "en": "what is this"},
        ], sents  # 1 cue = 1 句,原样(不合并/不补标点/不改大小写)
        js = d / "01_测试.json"
        js.write_text(json.dumps({"sentences": sents}, ensure_ascii=False), encoding="utf-8")
        errs, _ = check_pair(srt, js)
        assert not errs, errs  # 结构层自产必须全绿
        merged = {"sentences": [
            {"start": 1.2, "end": 4.5, "en": "How you doing?"},
            {"start": 6.1, "end": 7.9, "en": "what is this"},
        ]}
        js.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
        errs, _ = check_pair(srt, js)
        assert any("句数" in e for e in errs) and any("不一致" in e for e in errs), errs  # 合并被拦
        js.write_text(json.dumps({"sentences": sents[:2]}, ensure_ascii=False), encoding="utf-8")
        errs, _ = check_pair(srt, js)
        assert any("守恒" in e for e in errs), errs  # 丢句必须被守恒校验拦下
        drift = json.loads(json.dumps({"sentences": sents}))
        drift["sentences"][0]["en"] = "How you."  # 只加了标点也算改写
        js.write_text(json.dumps(drift, ensure_ascii=False), encoding="utf-8")
        errs, _ = check_pair(srt, js)
        assert any("不一致" in e for e in errs), errs
        bad = {"sentences": [{"start": 1.2, "end": 2.1, "en": "How you",
                              "words": [{"w": "hello", "phonetic": "/haɪ/"}]},
                             {"start": 2.3, "end": 4.5, "en": "doing?"},
                             {"start": 6.1, "end": 7.9, "en": "what is this"}]}
        js.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        errs, _ = check_pair(srt, js)
        assert any("表层连续片段" in e for e in errs) and any("斜杠" in e for e in errs), errs

        # 词组(表层连续片段)应合法,且须与 en 连续一致(跳词/颠倒即拦)
        srt2 = d / "02_词组.srt"
        srt2.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nhello boys and girls\n",
            encoding="utf-8",
        )
        js2 = d / "02_词组.json"
        ok_phrase = {"sentences": [
            {"start": 0.0, "end": 1.0, "en": "hello boys and girls",
             "words": [{"w": "boys and girls", "note": "男孩女孩们"}]},
        ]}
        js2.write_text(json.dumps(ok_phrase, ensure_ascii=False), encoding="utf-8")
        errs, _ = check_pair(srt2, js2)
        assert not errs, errs  # 词组合法

        bad_phrase = {"sentences": [
            {"start": 0.0, "end": 1.0, "en": "hello boys and girls",
             "words": [{"w": "boys girls"}]},
        ]}
        js2.write_text(json.dumps(bad_phrase, ensure_ascii=False), encoding="utf-8")
        errs, _ = check_pair(srt2, js2)
        assert any("表层连续片段" in e for e in errs), errs  # 跳词不连续,应拦
    print("selftest OK")


def main():
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)  # TextIOWrapper 才有
        if reconf:
            reconf(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="SRT→教学字幕 JSON 结构层工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft", help="SRT → 结构 JSON(1 cue = 1 句,en 定稿)")
    d.add_argument("path")
    d.add_argument("--force", action="store_true")
    c = sub.add_parser("check", help="校验富化后 JSON")
    c.add_argument("paths", nargs="+")
    sub.add_parser("selftest", help="内置样例自检")
    args = ap.parse_args()
    {"draft": cmd_draft, "check": cmd_check, "selftest": cmd_selftest}[args.cmd](args)


if __name__ == "__main__":
    main()
