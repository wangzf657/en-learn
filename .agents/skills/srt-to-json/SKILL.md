---
name: srt-to-json
description: SRT 转 EnLearn 启蒙教学字幕 JSON(按原始 cue 逐条富化 zh/words/note + 契约校验 + 导入交付;时间戳/台词为一等公民,禁止合并/拆分/改写)。Use when the user says "srt 转 json"、"转字幕"、"字幕转换"、"生成教学字幕"、"富化字幕" or wants a month folder of .srt files prepared for import. Use ONLY for converting existing English SRT text — ASR 从音频生成字幕是项目非目标,不做。
---

# SRT → 启蒙教学字幕 JSON

权威分工:数据结构以本 skill 目录下的 `subtitle.schema.json`(JSON Schema,机器可读)为准;校验分层、存储传输、前端时间轴等 app 侧说明见 `docs/design.md` §4;**生产流程与质量要求的唯一权威是本文件**(原 docs/srt-to-json-design.md、docs/subtitle-contract.md 已拆分并入删除)。数据结构冲突以 schema 为准,流程冲突以本文为准。

## 首要规则(凌驾一切,违反即返工)

**原 SRT 的 cue(时间戳 + 台词)是一等公民。** JSON 的 `sentences` 必须与 SRT 清洗后的 cue **逐条一一对应、顺序不变**:第 i 句的 `start/end` 就是第 i 个 cue 的起止时间,`en` 就是该 cue 的清洗后文本,**逐字符一致**。

- **禁止合并、禁止拆分、禁止改写**:不许把相邻两 cue 并成一句,不许把长 cue 拆成多句,不许补标点/改大小写/顺语法——哪怕看起来更通顺。结构只能由 `srt_tool.py` 从 SRT 机械生成,人和 agent 都不动。
- **不要关注句子长短**:20 词、30 词的长句照原样保留,半句话碎片也照原样保留。长度既不是拆分的理由,也不是合并的理由。
- 反面教训:agent 自造拆分点 = 时间戳是编造的,前端高亮与跟读评分全部错位,整批返工。
- 机器拦截:`check` 逐句比对 cue 的数量/时间戳/文本,任何漂移直接 ERROR,修不绿不交付。

## 架构取舍(为什么这样分层)

- **结构层**(解析/清洗/校验)= 本地确定性脚本:时间轴、cue 文本、`en` 词序列必须可复现、可 diff、可断点重跑——`en` 是跟读评分参考文本的地基,不交给概率性组件
- **语义层**(翻译/讲解/选词组)= 执行本 skill 的 agent(即 LLM)逐句完成:LLM 强于规则的地方;失败可整体重做,不污染结构
- 不用单遍 LLM 全做断句+富化:`en` 漂移风险高,守恒校验成了唯一防线且难归因
- **不建独立的 LLM API 批量工具**(旧设计规划的 `backend/tools/srt_to_json.py` 已废弃):agent 本身就是 LLM 富化路径,外部脚本是同一功能的重复实现,还要养 API key/重试/prompt;单机月度量级(≈30 视频)下无收益。真到要无人值守批量跑的程度再说

## 红线(违反即返工,check 子命令会机器拦截)

1. **`en` 与句边界一个都不能动**——它是跟读评分的参考文本(`reference = sentence.en`),也是前端高亮的时间轴,改了评分与对齐全错。**没有任何例外**(见"首要规则";结构只能由脚本从 SRT 机械生成)
2. **富化一旦开始,`en` 逐字冻结**:分句增量 edit 只加 `zh/words/note`;若整文件重写,`en` 必须逐字复制,且写完立即跑 check
3. `words.w` 是 `en` 中的**表层连续片段**——单词或词组皆可(如 `boys and girls`、`wake up`),照 `en` 原样:不增删词、不改词序、不还原词干(把 `doing` 写成 `do` 就错位)
4. `phonetic` 已废弃、不再生成;旧数据若带该键,仍须裸 IPA 不带首尾斜杠(check 仍校验)
5. `.json` **UTF-8 无 BOM**(BOM 会让按月导入把该视频整体跳过,原因"字幕 JSON 无效")
6. 句子按 `start` 升序、时间单调不重叠、`end > start`——前端高亮按 `start ≤ t < end` 命中,重叠/乱序直接表现为高亮跳变
7. 文本守恒:所有 `en` 拼接 == SRT 清洗后全文(没丢句、没造句、没改写)
8. check 有 ERROR 不交付;交付验收(流程 §5)走完才算完成

## 流程

### 0. 前置确认

- 月度文件夹形态:`NN_标题.mp4` + 同名 `.srt`(序号=日期,见 AGENTS.md 导入约定)
- 已存在同名 `.json` 时先问用户是否重做(重做加 `--force`,会覆盖已富化内容)
- 量大时(整月)一次会话做一支视频,做完一支 check 一支,不攒批——超长会话富化质量会漂移

### 1. 结构层(跑脚本,确定性)

```
backend\.venv\Scripts\python.exe .agents\skills\srt-to-json\scripts\srt_tool.py draft <文件夹|单个.srt> [--force]
```

脚本做:去 BOM/GBK 降级解码 → 逐 cue 清洗(HTML 标签、♪/`[music]` 注解行、说话人标签 `JOHN:`)→ **原样逐条成句(1 cue = 1 句:不组句、不补标点、不改大小写、时间戳原值)** → 写同名 `.json`(只含 `start/end/en`,至此全部冻结)。

- 清洗规则集中在脚本 `_clean()`:要改就改脚本后重跑 `draft --force`(会覆盖富化内容,慎用),不手改 JSON
- 实测:01-04 素材无 ♪/注解行误杀、无空 cue,清洗层零丢失

### 2. 结构冻结(没有人工调整窗口)

draft 生成的 `start/end/en` 即最终值,富化前后都不允许任何调整(见"首要规则")。碎片、长句、缺标点、大小写——一律照原样保留,由脚本机械决定;不手改 JSON。

- 怀疑清洗误杀/解析漏 cue:改 `srt_tool.py` 的清洗规则后重跑 draft(`--force` 会覆盖富化内容),不手改
- `check` 里"句数/时间戳/en 不一致"的 ERROR = 被改过,恢复原样重跑

### 3. 语义层(逐句填)

**先通读全片再动笔**:记下标题语境、角色名、口头禅的既有译名,全片(乃至同月系列)保持一致。

对每句补 `zh` / `words` / `note`,启蒙质量标准(每句就是原始 cue 的粒度:碎片按碎片译、长句按长句译,不补全、不拆分):

| 字段 | 标准 |
|---|---|
| `zh` | 准确、自然、口语化,符合儿童动画对白语气;不逐词硬译 |
| `words` | 每句通常 0–5 个(软上限,别堆砌);**优先选常用词组/固定搭配/短语**(`boys and girls`、`wake up`、`clean up`、`here you are` 这类),其次才是启蒙高频单字;不选 the/a/单一代词;**同一视频内同一条词组/单词最多讲一次,名额让给新词;选全别漏**(如 `boys and girls` 别只留 `boys` 漏掉 `girls`) |
| `words.w` | `en` 中的表层连续片段,照原样(词组含中间空格、单字含缩写/变形);不还原词干、不改词序 |
| `words.note` | ≤20 字中文,讲"整条什么意思、怎么说、什么时候说",不写词典腔 |
| `note`(句级) | ≤40 字句型/语法点;**宁缺毋滥**,没有教学价值就删键(前端当前也未渲染) |

### 4. 校验(必须 0 ERROR)

```
backend\.venv\Scripts\python.exe .agents\skills\srt-to-json\scripts\srt_tool.py check <文件夹>
```

脚本逐句比对 cue 数量/时间戳/文本(首要规则)+ 全文守恒 + words 契约;WARN(仅"words > 5 个")不拦;ERROR 必须修完重跑直到全绿——"不对齐/不一致"类 ERROR 说明结构或文本被改过,按 draft 原样恢复。

### 5. 交付与验收(闭环,走完才算完成)

1. check 全绿
2. 抽样自检:每支视频抽 3 句逐项过 §3 质量表,不合格回头改
3. 导入:Admin 页按月导入该文件夹(或 `POST /api/admin/videos/import`);幂等键 (date, video_path),同文件重导覆盖且保留 id 与打卡。**后端零改动**
4. 核对导入结果:返回的 `skipped[]` 里不能出现"字幕 JSON 无效";出现 = 回 §4 排查该文件

## 自检(改过脚本或 schema 后必跑)

```
backend\.venv\Scripts\python.exe .agents\skills\srt-to-json\scripts\srt_tool.py selftest
```

## 边界

- 不做 ASR 字幕生成(项目非目标);前提是已有 SRT 文本
- 转换是导入前的离线一次性步骤,App 运行时零云依赖不变
- 不做 `difficulty` 字段(无 UI 消费方)、不做 import 端 srt 兜底(保持导入端零逻辑)——真有需求再议
