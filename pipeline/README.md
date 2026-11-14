# Kakutora 翻译流水线工具链 (`pipeline/`)

基于 [文风.md](file:///d:/kakutora_translate/【翻译】/文风.md) 落地的四段式工具链：

## 1. Stage 0：构建单一权威词表 (SSOT)
```bash
python -m pipeline.build_glossary
```
合并 `【翻译】/专名/*.json` 与 `文风.md` 覆盖规则，生成 `pipeline/ssot_glossary.json`（含冲突记录）。

## 2. Stage 1：预扫描 & 生成本话 Context Pack
```bash
python -m pipeline.prescan stories/dd_ch01_05_010.json
# 支持通配符：
python -m pipeline.prescan "stories/dd_ch01_*.json"
```
输出到 `pipeline/work/<file>.context.md`，自动裁剪：
- 本话出场角色的口吻速查卡
- 本话命中的迷你专名表 & 语境歧义词
- 未收录的 `[专名]` 方括号链接
- 叙述诡计 / 内心世界潜入（司书顶着女主头衔）预警行号
- 恋之崎雅触发桂柳话的条目索引

## 3. Stage 3：安全回填译文并自动校验
准备轻量翻译包 JSON（支持 `entries` 或 `zhs` 两种格式）：
```json
{
  "file": "stories/dd_ch01_05_010.json",
  "title_zh": "...",
  "sub_title_zh": "...",
  "entries": [
    {"index": 0, "zh": "...", "narrator_zh": "..."}
  ]
}
```
执行回填（物理锁死原文字段，自动运行 Stage 4 校验）：
```bash
python -m pipeline.apply_pack path/to/pack.json
```

## 4. Stage 4：批量自动化 Linter
```bash
python -m pipeline.lint "【翻译】/stories/dd_ch02_*.json"
python -m pipeline.lint "【翻译】/stories/*.json" --errors-only
```
检查：原文字段完整性、换行符一致、`<color>`/`$me$`/`<meta>` 标记匹配、`[专名]` 词表一致、假名残留、雅桂柳话禁用词、神乐 `pyon` 滥用、`なう/now` 残留、`[?]` 待校对汇总。

## 5. 随读笔记模板（单角色全线共有：`【翻译】/随读笔记/chXX_<角色>.md`）
由主仓库统一追踪版本历史。单份笔记**总体积控制在 ~2000 tokens 内（主线滑窗与状态快照约 1500 tokens）**，采用「长期关键锚点 + 近 3~4 章主线滑窗 + 合并口吻卡」结构：
```markdown
# chXX 角色线 · 随读笔记
## 1. 长期关键锚点与未解疑点（不随滑窗过期，已解即删）
- **关键关系转折 / 未解核心疑点 / 固定称呼**
## 2. 近期主线滑窗（保留近 3~4 章的因果、情绪转折与关键场景）
- **XX（章节名）**：保留足够支撑语气连贯的剧情脉络；额外剧情仅摘录显露角色反差或新增人物/称呼的要点。
## 3. 司书与角色口吻（合并提炼，保留对比句例）
- **角色/司书名**：不同情境下的语气切换、自称、称呼与代表例句。
## 4. 跨章未决 `[?]`（解决即删）
- 仅保留需后文才能定夺的伏笔/译法。
```
每次更新或压缩笔记后，在根目录单独提交一条 commit：`git add "【翻译】/随读笔记" && git commit -m "notes: chXX_YY"`。
