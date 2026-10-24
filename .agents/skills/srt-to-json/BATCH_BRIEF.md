# 批量提炼作业细则(V2.0 存量迁移,一次性)

> 权威:同目录 `SKILL.md`(先完整读一遍,尤其**「首要规则」**与 **§2 语义层/§3 质量标准**);冲突以 SKILL.md 为准。本文只补"批量作业"的操作细节。

## 1. 任务

把旧格式 json(全量逐句富化:`{"sentences": [全部句 zh/words/note]}`)重新提炼为 **V2.0 带学练习卡**(四板:`words/sentences/dialogues/guide`,见 `subtitle.schema.json`),同文件名写回。旧数据不再是交付形态——播放页已不消费全量台词。

## 2. 批量前置(必做,顺序不可颠倒)

1. **核对落盘路径**:成品必须写在素材同名文件夹内的同名文件 `NN_标题/NN_标题.json`——后端导入只查这个位置。开工前抽查 2 个文件确认路径形态,拿不准先停下来问。
2. **备份旧 json**:把每支视频的旧 `NN_标题.json` 复制到课程文件夹下的 `_v1_backup/NN_标题.json`(该文件夹不是任何 mp4 的同名文件夹,导入与复习中心都不会扫它)。备份做完才允许覆盖。
3. 确认没有会话正在跑 `draft --force`。

## 3. 逐文件流程

1. **读旧 json 全文 + 看 mp4 标题**(先通读再动笔;留意角色名,译名全批一致。常见:Steve=史蒂夫,Maggie=玛吉)。
2. **提炼四板**(标准见 SKILL.md §2 表格与 §3):
   - `sentences` 3–6 句:从旧 json 里**选**重点短句,`en/start/end/zh` 直接从旧 json 逐字复制(`note` 可留可删);不选不造不改
   - `words` 4–8 条:优先从旧 json 各句 `words` 里挑值得掌握的词组(`w/note` 可复用,补 `zh`);不够再从全文自选,`w` 必须是本集原声文本的表层连续片段
   - `dialogues` 1–3 个 + `guide`:全新生成,围绕本集核心词句拓展日常场景与带学脚本
3. **写回**:用 write 工具整文件重写同名 `.json`,2 空格缩进、UTF-8 无 BOM(不要用 PowerShell Set-Content)。旧 json 顶层只保留四板,其余键(包括全量 sentences)不再保留。
4. **写完立即校验(逐文件)**:

   ```
   backend\.venv\Scripts\python.exe .agents\skills\srt-to-json\scripts\srt_tool.py check "<同名.srt>" "<该.json>"
   ```

   必须 `OK`(0 ERROR)。若报"不是原声句/时间戳不对齐" = `en/start/end` 被动过:对照旧 json 或重跑 `draft --force` 后重做。WARN 不拦截,记录即可。若你的环境不能执行命令,跳过并在回报中注明"未跑 check"。
5. 不碰分配清单以外的任何文件;不要对未分配的文件夹跑 `draft --force`。

## 4. 回报格式(全批做完后)

- 每文件一行:`文件名 → OK`(或 `WARN n`);未跑 check 的注明"未跑 check"。
- 不确定项:拿不准的译名/存疑台词(没有就写"无")。

## 5. 收尾(全批绿后)

- 提醒用户:Admin 页重导对应课程文件夹(幂等,`rel_path` 键,重导 UPDATE id 稳定、排期/打卡不受影响);导入返回的 `skipped[]` 里不能出现"字幕 JSON 无效"。
- `_v1_backup/` 保留至用户确认新版无回退需求,由用户手动删除。
