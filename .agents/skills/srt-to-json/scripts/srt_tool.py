#!/usr/bin/env python3
"""EnLearn SRT→带学练习卡 JSON(V2.0 提炼式)的结构层工具与校验器。

结构权威:subtitle.schema.json(本 skill 目录);流程与质量要求:.agents/skills/srt-to-json/SKILL.md。

V2.0 契约:成品 JSON 是四板提炼(重点单词 words / 重点短句 sentences / 亲子对话
dialogues / 家长带学 guide),不再包含全量台词。原声句仍是一等公民:sentences 必须
是 SRT 清洗合并后原声句的「重点子集」(en 逐字、start/end 逐秒一致,只能选不能造);
words.w 是全集文本的表层连续词块;dialogues/guide 是生成内容(结构+枚举校验)。

用法:
  python srt_tool.py draft <文件夹 | 单个.srt> [--force]   # SRT → 全量句骨架(提炼候选池)
  python srt_tool.py check <文件夹 | a.srt a.json>         # 四板契约 + 子集对齐校验
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

# 数量软上限(超出仅 WARN,见 SKILL.md §2)
WORDS_LIMIT = 8
SENTENCES_LIMIT = 6
DIALOGUES_LIMIT = 3
DIALOGUE_LINES_LIMIT = 8
SPEAKERS = ("parent", "child")


def _tokens(s: str):
    """切词:保留缩写内部撇号(don't),剥掉作引号的边缘撇号('Dig!' → dig)。"""
    toks = (tok.strip("'").lower() for tok in re.findall(r"[A-Za-z']+", s.replace("\u2019", "'")))
    return [t for t in toks if t]


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


def subtitle_json_path(srt: Path) -> Path:
    """成品 JSON 的落盘位置(导入契约,见 main.py 导入逻辑):素材同名文件夹 `<stem>/<stem>.json`,与 mp4 同级。

    srt 已在同名文件夹内(规范形态)时,就是 srt 旁的同名 .json;
    srt 平铺在课程文件夹时,落同名子文件夹(目录不存在由 draft 创建)。
    """
    if srt.parent.name == srt.stem:
        return srt.with_suffix(".json")
    return srt.parent / srt.stem / (srt.stem + ".json")


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
    return _merge_karaoke(_normalize(cues))


def _normalize(cues):
    """源 SRT 时间轴缺陷的确定性清洗(卡拉OK式逐词高亮字幕常见),保单调不重叠:

    1. 首尾颠倒(end < start,1ms 级零长高亮帧)→ 交换起止
    2. 相邻 cue 重叠(高亮 cue 常提前开始,几毫秒到几百毫秒)→ 上一 cue 的 end 钳到本 cue 的 start
    3. 仍零长(end ≤ start)→ 补 1ms,保 end > start;若因此压到下一 cue 再钳一次
    """
    for c in cues:
        if c["end"] < c["start"]:
            c["start"], c["end"] = c["end"], c["start"]
    for i in range(1, len(cues)):
        prev, cur = cues[i - 1], cues[i]
        if cur["start"] < prev["end"]:
            prev["end"] = cur["start"]
    for c in cues:
        if c["end"] <= c["start"]:
            c["end"] = c["start"] + 0.001
    for i in range(1, len(cues)):
        prev, cur = cues[i - 1], cues[i]
        if cur["start"] < prev["end"]:
            cur["start"] = prev["end"]
            if cur["end"] <= cur["start"]:
                cur["end"] = cur["start"] + 0.001
    return cues


def _merge_karaoke(cues):
    """卡拉OK式逐词高亮源的确定性合并:相邻同文 cue 并为一句,时间取并集。

    同一句在源里每个单词高亮一步就重复一条 cue(常再补一条整句长条),剥标签后
    文本完全一致;按"相邻同文"判定(不跨非同文 cue),语义层一句只留一条。
    须在 _normalize 之后调用(时间轴已单调不重叠,末条 end 即并集上界)。
    """
    out = []
    for c in cues:
        if out and c["text"] == out[-1]["text"]:
            out[-1]["end"] = c["end"]
            continue
        out.append(dict(c))
    return out


def _span_in(tokens, need):
    """need 是否为 tokens 的连续子序列(两侧已统一小写/撇号)。

    单元素 = 单词须精确命中 token;多元素 = 词组须与一段连续词完全一致。
    """
    return any(tokens[i : i + len(need)] == need for i in range(len(tokens) - len(need) + 1))


def _nonempty_str(v):
    return isinstance(v, str) and v.strip()


def check_pair(srt: Path, js: Path):
    """校验提炼后的 JSON(V2.0 四板契约)。返回 (errors, warnings);errors 非空 = 不可交付。"""
    errs, warns = [], []
    try:
        data = json.loads(js.read_text(encoding="utf-8-sig"))
    except Exception as e:
        return [f"{js.name}: JSON 解析失败: {e}"], []
    if not isinstance(data, dict):
        return [f"{js.name}: 必须是对象"], []
    cues = parse_srt(srt)
    cue_map = {}  # 原声句精确文本 → [(start, end)](同文句可多次出现)
    for c in cues:
        cue_map.setdefault(c["text"], []).append((c["start"], c["end"]))
    full_tokens = _tokens(" ".join(c["text"] for c in cues))  # words 板的比对基准

    def check_text(tag, s):
        """en 类文本公共检查:非空、无首尾空白、无 HTML 残留。"""
        if not s.strip():
            errs.append(f"{tag}: 文本为空")
        if s != s.strip():
            errs.append(f"{tag}: 首尾有空白")
        if TAG_RE.search(s):
            errs.append(f"{tag}: 残留 HTML 标签")

    boards = 0

    # ---- sentences:重点短句(原声句的重点子集,只能选不能造) ----
    sents = data.get("sentences")
    if sents is not None:
        if not isinstance(sents, list):
            errs.append(f"{js.name}: sentences 必须是数组")
        else:
            boards += 1 if sents else 0  # 空数组不占板块(防空壳)
            if len(sents) > SENTENCES_LIMIT:
                warns.append(f"{js.name}: sentences {len(sents)} 句 > {SENTENCES_LIMIT},建议精简")
            if len(sents) < 3:
                warns.append(f"{js.name}: sentences 仅 {len(sents)} 句 < 3,建议补选")
            seen, prev_start = set(), None
            for i, s in enumerate(sents):
                tag = f"{js.name} 第{i + 1}句"
                if not isinstance(s, dict):
                    errs.append(f"{tag}: 不是对象")
                    continue
                en = s.get("en")
                if not isinstance(en, str):
                    errs.append(f"{tag}: en 必须字符串(服务端 422)")
                    continue
                check_text(tag, en)
                st, ed = s.get("start"), s.get("end")
                if not isinstance(st, (int, float)) or not isinstance(ed, (int, float)):
                    errs.append(f"{tag}: start/end 必须数字")
                else:
                    if ed <= st:
                        errs.append(f"{tag}: end 必须大于 start")
                    if prev_start is not None and st < prev_start:
                        errs.append(f"{tag}: 与上一句乱序(按 start 升序)")
                    prev_start = st
                    hits = cue_map.get(en)
                    if hits is None:
                        errs.append(f"{tag}: 不是原声句「{en[:60]}」(只能选,不能造/改写)")
                    elif not any(
                        abs(st - a) <= ALIGN_TOL and abs(ed - b) <= ALIGN_TOL for a, b in hits
                    ):
                        a, b = hits[0]
                        errs.append(
                            f"{tag}: 时间戳与原声 cue 不对齐(原 {a:g}–{b:g},现 {st:g}–{ed:g})"
                        )
                if en in seen:
                    warns.append(f"{tag}: 重复选择同一句")
                seen.add(en)
                if not _nonempty_str(s.get("zh")):
                    errs.append(f"{tag}: zh 必填(V2.0 生成契约)")
                n = s.get("note")
                if n is not None and not _nonempty_str(n):
                    errs.append(f"{tag}: note 空串(删掉该键)")

    # ---- words:重点单词/词块(全集表层连续片段) ----
    ws = data.get("words")
    if ws is not None:
        if not isinstance(ws, list):
            errs.append(f"{js.name}: words 必须是数组")
        else:
            boards += 1 if ws else 0
            if len(ws) > WORDS_LIMIT:
                warns.append(f"{js.name}: words {len(ws)} 条 > {WORDS_LIMIT},建议精简")
            for j, w in enumerate(ws):
                wtag = f"{js.name} words[{j}]"
                if not isinstance(w, dict) or not _nonempty_str(w.get("w")):
                    errs.append(f"{wtag}: 缺 w 或非字符串")
                    continue
                w_tokens = _tokens(w["w"])
                if not w_tokens:
                    errs.append(f"{wtag}: w '{w['w']}' 不含有效词")
                elif not _span_in(full_tokens, w_tokens):
                    errs.append(f"{wtag}: w '{w['w']}' 不是本集原声文本的表层连续片段")
                if not _nonempty_str(w.get("zh")):
                    errs.append(f"{wtag}: zh 必填(V2.0 生成契约)")
                n = w.get("note")
                if n is not None and not _nonempty_str(n):
                    errs.append(f"{wtag}: note 空串(删掉该键)")

    # ---- dialogues:亲子场景对话(生成内容,结构+枚举校验) ----
    ds = data.get("dialogues")
    if ds is not None:
        if not isinstance(ds, list):
            errs.append(f"{js.name}: dialogues 必须是数组")
        else:
            boards += 1 if ds else 0
            if len(ds) > DIALOGUES_LIMIT:
                warns.append(f"{js.name}: dialogues {len(ds)} 个 > {DIALOGUES_LIMIT},建议精简")
            for i, d in enumerate(ds):
                dtag = f"{js.name} dialogues[{i}]"
                if not isinstance(d, dict):
                    errs.append(f"{dtag}: 不是对象")
                    continue
                if not _nonempty_str(d.get("scene")):
                    errs.append(f"{dtag}: 缺 scene(非空中文场景名)")
                lines = d.get("lines")
                if not isinstance(lines, list) or not lines:
                    errs.append(f"{dtag}: lines 必须是非空数组")
                    continue
                if len(lines) > DIALOGUE_LINES_LIMIT:
                    warns.append(f"{dtag}: lines {len(lines)} 行 > {DIALOGUE_LINES_LIMIT},建议精简")
                for k, ln in enumerate(lines):
                    ltag = f"{dtag} lines[{k}]"
                    if not isinstance(ln, dict):
                        errs.append(f"{ltag}: 不是对象")
                        continue
                    en = ln.get("en")
                    if not _nonempty_str(en):
                        errs.append(f"{ltag}: 缺 en")
                    else:
                        check_text(ltag, en)
                    if ln.get("speaker") not in SPEAKERS:
                        errs.append(f"{ltag}: speaker 必须是 parent/child")
                    if not _nonempty_str(ln.get("zh")):
                        errs.append(f"{ltag}: zh 必填")
                tip = d.get("tip")
                if tip is not None and not _nonempty_str(tip):
                    errs.append(f"{dtag}: tip 空串(删掉该键)")

    # ---- guide:家长带学脚本 ----
    g = data.get("guide")
    if g is not None:
        if not isinstance(g, dict):
            errs.append(f"{js.name}: guide 必须是对象")
        else:
            boards += 1 if g else 0
            if not _nonempty_str(g.get("goal")):
                errs.append(f"{js.name}: guide.goal 必填(一句话目标)")
            for key in ("before", "after"):
                v = g.get(key)
                if not isinstance(v, list) or not v:
                    errs.append(f"{js.name}: guide.{key} 必填且至少 1 条")
                else:
                    for k, item in enumerate(v):
                        if not _nonempty_str(item):
                            errs.append(f"{js.name}: guide.{key}[{k}] 空串")
            for key in ("during", "tips"):
                v = g.get(key)
                if v is None:
                    continue
                if not isinstance(v, list):
                    errs.append(f"{js.name}: guide.{key} 必须是数组")
                else:
                    for k, item in enumerate(v):
                        if not _nonempty_str(item):
                            errs.append(f"{js.name}: guide.{key}[{k}] 空串")

    if boards == 0:
        errs.append(f"{js.name}: 四板(words/sentences/dialogues/guide)至少一板存在")
    if (
        isinstance(sents, list)
        and len(sents) == len(cues)
        and ws is None and ds is None and g is None
    ):
        warns.append(f"{js.name}: 疑似旧格式(全量台词 {len(sents)} 句、无其他板块),需按 V2.0 重新提炼")
    return errs, warns


def cmd_draft(args):
    src = Path(args.path)
    srts = sorted(src.rglob("*.srt")) if src.is_dir() else [src]
    if not srts or not all(p.is_file() for p in srts):
        sys.exit(f"ERROR 找不到 SRT: {args.path}")
    for srt in srts:
        out = subtitle_json_path(srt)
        if out.exists() and not args.force:
            print(f"SKIP {out}(已存在,--force 覆盖)")
            continue
        cues = parse_srt(srt)
        sents = [{"start": c["start"], "end": c["end"], "en": c["text"]} for c in cues]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"sentences": sents}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"DRAFT {out}: {len(sents)} 句候选池(相邻同文卡拉OK cue 已合并;供 AI 提炼,非交付形态)")


def cmd_check(args):
    paths = [Path(p) for p in args.paths]
    if len(paths) == 1 and paths[0].is_dir():
        pairs = []
        for srt in sorted(paths[0].rglob("*.srt")):
            js = subtitle_json_path(srt)
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

KARAOKE_SRT = """1
00:00:32,808 --> 00:00:33,245\nRaccoon: Watch me hop!

2
00:00:33,246 --> 00:00:33,503
Raccoon: <font color="#ffff00">Watch</font> me hop!

3
00:00:33,504 --> 00:00:33,733
Raccoon: Watch <font color="#ffff00">me</font> hop!

4
00:00:33,734 --> 00:00:34,188
Raccoon: Watch me <font color="#ffff00">hop</font>!

5
00:00:34,189 --> 00:00:40,535\nRaccoon: Watch me hop!

6
00:00:40,536 --> 00:00:41,260\nTurtle: I can't hop.
"""


def _write(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_selftest(args):
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)

        # --- 结构层(draft 层,与 V1 相同):清洗/落盘契约/时间轴规范化/卡拉OK合并 ---
        sub = d / "01_测试"  # 规范形态:srt/json 都在素材同名文件夹内
        sub.mkdir()
        srt = sub / "01_测试.srt"
        srt.write_bytes(b"\xef\xbb\xbf" + SAMPLE_SRT.encode("utf-8"))  # 带 BOM 验证解码
        cues = parse_srt(srt)
        assert len(cues) == 3, cues  # ♪ 音乐行被清洗丢弃
        sents = [{"start": c["start"], "end": c["end"], "en": c["text"]} for c in cues]
        assert sents == [
            {"start": 1.2, "end": 2.1, "en": "How you"},
            {"start": 2.3, "end": 4.5, "en": "doing?"},
            {"start": 6.1, "end": 7.9, "en": "what is this"},
        ], sents  # 1 cue = 1 句,原样(不合并/不补标点/不改大小写)
        js = srt.with_suffix(".json")
        assert subtitle_json_path(srt) == js  # 落盘位置符合导入契约

        # 源时间轴缺陷的确定性清洗:重叠钳位 / 首尾颠倒交换 / 零长补 1ms
        sub3 = d / "03_缺陷"
        sub3.mkdir()
        srt3 = sub3 / "03_缺陷.srt"
        srt3.write_text(
            "1\n00:00:10,000 --> 00:00:11,000\nA\n\n"
            "2\n00:00:10,800 --> 00:00:12,000\nB\n\n"
            "3\n00:00:12,001 --> 00:00:12,000\nC\n\n"
            "4\n00:00:12,001 --> 00:00:12,001\nD\n",
            encoding="utf-8",
        )
        assert [(round(c["start"], 6), round(c["end"], 6)) for c in parse_srt(srt3)] == [
            (10.0, 10.8),  # 重叠 200ms:上一 cue end 钳到本 cue start
            (10.8, 12.0),
            (12.0, 12.001),  # 首尾颠倒:交换起止
            (12.001, 12.002),  # 零长 cue:补 1ms
        ]

        # 卡拉OK式逐词高亮源:同句每步一条 cue,相邻同文机械合并为一句(时间取并集)
        sub4 = d / "04_卡拉OK"
        sub4.mkdir()
        srt4 = sub4 / "04_卡拉OK.srt"
        srt4.write_text(KARAOKE_SRT, encoding="utf-8")
        assert [(round(c["start"], 6), round(c["end"], 6), c["text"]) for c in parse_srt(srt4)] == [
            (32.808, 40.535, "Raccoon: Watch me hop!"),  # 5 条同文 cue 并 1 句
            (40.536, 41.26, "Turtle: I can't hop."),  # 下一句不同文,不并入
        ]

        # --- V2.0 提炼式 check ---
        js4 = subtitle_json_path(srt4)

        good = {
            "words": [
                {"w": "Watch me hop", "zh": "看我跳", "note": "邀人看自己动作"},
                {"w": "hop", "zh": "跳"},
            ],
            "sentences": [
                {"start": 32.808, "end": 40.535, "en": "Raccoon: Watch me hop!", "zh": "浣熊:看我跳!"},
                {"start": 40.536, "end": 41.26, "en": "Turtle: I can't hop.", "zh": "乌龟:我不会跳。"},
            ],
            "dialogues": [
                {
                    "scene": "一起来跳",
                    "lines": [
                        {"speaker": "parent", "en": "Watch me hop!", "zh": "看我跳!"},
                        {"speaker": "child", "en": "I can hop too!", "zh": "我也能跳!"},
                        {"speaker": "parent", "en": "Great job!", "zh": "跳得真棒!"},
                    ],
                    "tip": "边说边跳",
                }
            ],
            "guide": {
                "goal": "听懂 hop,说出 Watch me hop",
                "before": ["跟孩子说:乌龟不会跳,你猜谁会跳?"],
                "after": ["hop 用英语怎么说?"],
                "tips": ["hop 短促有力,别拖成 hooop"],
            },
        }
        _write(js4, good)
        errs, warns = check_pair(srt4, js4)
        assert not errs, errs  # 四板齐、子集对齐、词块在全文 → 全绿

        drift = json.loads(json.dumps(good))
        drift["sentences"][0]["en"] = "Raccoon: Watch me JUMP!"  # 改写原声句
        _write(js4, drift)
        errs, _ = check_pair(srt4, js4)
        assert any("不是原声句" in e for e in errs), errs

        drift = json.loads(json.dumps(good))
        drift["sentences"][0]["start"] = 33.5  # 时间戳漂移
        _write(js4, drift)
        errs, _ = check_pair(srt4, js4)
        assert any("不对齐" in e for e in errs), errs

        drift = json.loads(json.dumps(good))
        drift["sentences"][0]["zh"] = ""  # zh 缺失(生成契约)
        _write(js4, drift)
        errs, _ = check_pair(srt4, js4)
        assert any("zh 必填" in e for e in errs), errs

        drift = json.loads(json.dumps(good))
        drift["words"][0]["w"] = "jump"  # 不在原声文本
        _write(js4, drift)
        errs, _ = check_pair(srt4, js4)
        assert any("表层连续片段" in e for e in errs), errs

        drift = json.loads(json.dumps(good))
        drift["dialogues"][0]["lines"][0]["speaker"] = "teacher"  # 枚举外
        _write(js4, drift)
        errs, _ = check_pair(srt4, js4)
        assert any("speaker" in e for e in errs), errs

        drift = json.loads(json.dumps(good))
        del drift["guide"]["after"]  # guide 必填键
        _write(js4, drift)
        errs, _ = check_pair(srt4, js4)
        assert any("guide.after" in e for e in errs), errs

        drift = json.loads(json.dumps(good))
        drift["words"], drift["sentences"], drift["dialogues"], drift["guide"] = [], [], [], {}
        _write(js4, drift)
        errs, _ = check_pair(srt4, js4)
        assert any("至少一板" in e for e in errs), errs

        # 旧格式(全量台词+zh、无其他板块):结构上合法,但 WARN 提示重新提炼
        old = {"sentences": [
            {"start": 32.808, "end": 40.535, "en": "Raccoon: Watch me hop!", "zh": "浣熊:看我跳!"},
            {"start": 40.536, "end": 41.26, "en": "Turtle: I can't hop.", "zh": "乌龟:我不会跳。"},
        ]}
        _write(js4, old)
        errs, warns = check_pair(srt4, js4)
        assert not errs and any("旧格式" in w for w in warns), (errs, warns)

        # draft 骨架(未提炼):不是原声句的问题没有,但 zh 必填全 ERROR = 不可交付
        skeleton = {"sentences": [{"start": c["start"], "end": c["end"], "en": c["text"]} for c in parse_srt(srt4)]}
        _write(js4, skeleton)
        errs, _ = check_pair(srt4, js4)
        assert any("zh 必填" in e for e in errs), errs

        # 单引号包裹的词('Dig!')应能匹配:作引号的撇号不并入词元
        sub5 = d / "05_引号"
        sub5.mkdir()
        srt5 = sub5 / "05_引号.srt"
        srt5.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n\"It says, 'Dig!'\" Zippy said.\n",
            encoding="utf-8",
        )
        js5 = subtitle_json_path(srt5)
        quoted = {
            "words": [{"w": "Dig", "zh": "挖"}],
            "sentences": [
                {"start": 0.0, "end": 1.0, "en": "\"It says, 'Dig!'\" Zippy said.", "zh": "「上面写着:挖!」齐比说。"}
            ],
            "guide": {"goal": "听懂 dig", "before": ["x"], "after": ["y"]},
        }
        _write(js5, quoted)
        errs, _ = check_pair(srt5, js5)
        assert not errs, errs  # 引号撇号不算词的一部分
    print("selftest OK")


def main():
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)  # TextIOWrapper 才有
        if reconf:
            reconf(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="SRT→带学练习卡 JSON(V2.0)结构层工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft", help="SRT → 全量句骨架(提炼候选池,en 定稿)")
    d.add_argument("path")
    d.add_argument("--force", action="store_true")
    c = sub.add_parser("check", help="校验提炼后 JSON(四板契约)")
    c.add_argument("paths", nargs="+")
    sub.add_parser("selftest", help="内置样例自检")
    args = ap.parse_args()
    {"draft": cmd_draft, "check": cmd_check, "selftest": cmd_selftest}[args.cmd](args)


if __name__ == "__main__":
    main()
