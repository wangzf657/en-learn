#!/usr/bin/env python3
"""EnLearn SRT→教学字幕 JSON 的结构层工具与校验器。

结构权威:subtitle.schema.json(本 skill 目录);流程与质量要求:.agents/skills/srt-to-json/SKILL.md。

首要规则:清洗后的"句"是一等公民 = 逐条独立 cue;卡拉OK式逐词高亮源(同句每高亮
一词就重复一条 cue)的**相邻同文 cue 由脚本机械合并为一句**,时间取并集。JSON 的
sentences 与合并后的句一一对应(数量、顺序、start/end、en 文本全一致);除该合并外
禁止合并/拆分/改写,人和 agent 都不动结构,一切以原 SRT 为准。

用法:
  python srt_tool.py draft <文件夹 | 单个.srt> [--force]   # SRT → 结构 JSON(自动合并卡拉OK同文 cue)
  python srt_tool.py check <文件夹 | a.srt a.json>         # 契约 + 逐句对齐 + 守恒校验
  python srt_tool.py dedup <文件夹 | 单个.srt>             # 存量修复:就地合并旧 json 的相邻同文句
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
    """源 SRT 时间轴缺陷的确定性清洗(卡拉OK式逐词高亮字幕常见),保证红线 6:

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


def _merge_sents(sents):
    """成品 JSON 句条目的合并(dedup 存量修复用):同 _merge_karaoke,键为 en,
    并把后条的 zh/note/words 回填给首条(仅首条缺失时)——富化内容一条不丢。"""
    out = []
    for s in sents:
        prev = out[-1] if out else None
        if prev is not None and s.get("en") == prev.get("en"):
            prev["end"] = s["end"]
            for k in ("zh", "note"):
                cur = prev.get(k)
                if not (isinstance(cur, str) and cur.strip()):
                    nv = s.get(k)
                    if isinstance(nv, str) and nv.strip():
                        prev[k] = nv
            if not prev.get("words") and s.get("words"):
                prev["words"] = s["words"]
            continue
        out.append(dict(s))
    return out


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

    # 首要规则:逐句与原句(卡拉OK同文 cue 已合并)对齐(数量/时间戳/文本)
    if len(sents) != len(cues):
        errs.append(
            f"{js.name}: 句数 {len(sents)} ≠ 原 SRT 句数 {len(cues)}"
            f"(卡拉OK同文 cue 已由脚本合并;禁止再合并/拆分/增删)"
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
                tokens = _tokens(en)
                for j, w in enumerate(ws):
                    wtag = f"{tag} words[{j}]"
                    if not isinstance(w, dict) or not isinstance(w.get("w"), str) or not w["w"].strip():
                        errs.append(f"{wtag}: 缺 w 或非字符串")
                        continue
                    w_tokens = _tokens(w["w"])
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
        print(f"DRAFT {out}: {len(sents)} 句(相邻同文卡拉OK cue 已合并)")


def cmd_dedup(args):
    """存量修复:旧规则生成的成品 JSON(卡拉OK重复条未合并)就地机械合并。

    只按"相邻同文"合并,zh/note/words 富化字段一条不丢;合并后立即 check 全绿才算过。
    """
    src = Path(args.path)
    srts = sorted(src.rglob("*.srt")) if src.is_dir() else [src]
    if not srts or not all(p.is_file() for p in srts):
        sys.exit(f"ERROR 找不到 SRT: {args.path}")
    failed = False
    for srt in srts:
        js = subtitle_json_path(srt)
        if not js.exists():
            print(f"MISS {srt.stem}(无 json)")
            continue
        try:
            data = json.loads(js.read_text(encoding="utf-8-sig"))
        except Exception as e:
            print(f"ERROR {js.name}: JSON 解析失败: {e}")
            failed = True
            continue
        sents = data.get("sentences") if isinstance(data, dict) else None
        if not isinstance(sents, list):
            print(f"ERROR {js.name}: 必须是含 sentences 数组的对象")
            failed = True
            continue
        merged = _merge_sents(sents)
        if len(merged) == len(sents):
            print(f"OK {js.name}: 无相邻重复,{len(sents)} 句")
            continue
        data["sentences"] = merged
        js.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        errs, _ = check_pair(srt, js)
        if errs:
            failed = True
            for e in errs:
                print(f"ERROR {e}")
        else:
            print(f"MERGED {js.name}: {len(sents)} → {len(merged)} 句(check 全绿)")
    sys.exit(1 if failed else 0)


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


def cmd_selftest(args):
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
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
        srt4.write_text(
            "1\n00:00:32,808 --> 00:00:33,245\nRaccoon: Watch me hop!\n\n"
            "2\n00:00:33,246 --> 00:00:33,503\n"
            'Raccoon: <font color="#ffff00">Watch</font> me hop!\n\n'
            "3\n00:00:33,504 --> 00:00:33,733\n"
            'Raccoon: Watch <font color="#ffff00">me</font> hop!\n\n'
            "4\n00:00:33,734 --> 00:00:34,188\n"
            'Raccoon: Watch me <font color="#ffff00">hop</font>!\n\n'
            "5\n00:00:34,189 --> 00:00:40,535\nRaccoon: Watch me hop!\n\n"
            "6\n00:00:40,536 --> 00:00:41,260\nTurtle: I can't hop.\n",
            encoding="utf-8",
        )
        assert [(round(c["start"], 6), round(c["end"], 6), c["text"]) for c in parse_srt(srt4)] == [
            (32.808, 40.535, "Raccoon: Watch me hop!"),  # 5 条同文 cue 并 1 句
            (40.536, 41.26, "Turtle: I can't hop."),  # 下一句不同文,不并入
        ]
        js4 = subtitle_json_path(srt4)
        sents4 = [{"start": c["start"], "end": c["end"], "en": c["text"]} for c in parse_srt(srt4)]
        js4.write_text(json.dumps({"sentences": sents4}, ensure_ascii=False), encoding="utf-8")
        errs, _ = check_pair(srt4, js4)
        assert not errs, errs  # 合并形态与 check 自洽

        # dedup 存量修复:旧 json(重复条未合并,zh 全条都有、words 只在首条)→ 合并不丢富化
        old = [
            {"start": 32.808, "end": 33.245, "en": "Raccoon: Watch me hop!", "zh": "浣熊:看我跳!"},
            {"start": 33.246, "end": 33.503, "en": "Raccoon: Watch me hop!", "zh": "浣熊:看我跳!"},
            {"start": 33.504, "end": 34.188, "en": "Raccoon: Watch me hop!", "zh": "浣熊:看我跳!"},
            {"start": 34.189, "end": 40.535, "en": "Raccoon: Watch me hop!", "zh": "浣熊:看我跳!"},
        ]
        old[0]["words"] = [{"w": "watch", "note": "看"}]
        m = _merge_sents(old)
        assert len(m) == 1, m
        assert (round(m[0]["start"], 6), round(m[0]["end"], 6)) == (32.808, 40.535), m
        assert m[0]["zh"] == "浣熊:看我跳!" and m[0]["words"] == [{"w": "watch", "note": "看"}], m
        m2 = _merge_sents([  # 首条缺 zh 时由后条回填
            {"start": 1.0, "end": 2.0, "en": "Hi."},
            {"start": 2.0, "end": 3.0, "en": "Hi.", "zh": "你好。"},
        ])
        assert m2[0]["zh"] == "你好。" and round(m2[0]["end"], 6) == 3.0, m2

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
        sub2 = d / "02_词组"
        sub2.mkdir()
        srt2 = sub2 / "02_词组.srt"
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

        # 单引号包裹的词('Dig!')应能匹配:作引号的撇号不并入词元
        sub5 = d / "05_引号"
        sub5.mkdir()
        srt5 = sub5 / "05_引号.srt"
        srt5.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n\"It says, 'Dig!'\" Zippy said.\n",
            encoding="utf-8",
        )
        js5 = sub5 / "05_引号.json"
        quoted = {"sentences": [
            {"start": 0.0, "end": 1.0, "en": "\"It says, 'Dig!'\" Zippy said.",
             "words": [{"w": "Dig", "note": "挖"}]},
        ]}
        js5.write_text(json.dumps(quoted, ensure_ascii=False), encoding="utf-8")
        errs, _ = check_pair(srt5, js5)
        assert not errs, errs  # 引号撇号不算词的一部分
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
    dd = sub.add_parser("dedup", help="存量修复:就地合并成品 JSON 相邻同文句(卡拉OK重复)")
    dd.add_argument("path")
    sub.add_parser("selftest", help="内置样例自检")
    args = ap.parse_args()
    {"draft": cmd_draft, "check": cmd_check, "dedup": cmd_dedup, "selftest": cmd_selftest}[args.cmd](args)


if __name__ == "__main__":
    main()
