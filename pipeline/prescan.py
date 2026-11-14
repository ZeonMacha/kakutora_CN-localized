# -*- coding: utf-8 -*-
"""Stage 1: Pre-scan a source JSON file and generate a compact Context Pack."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from pipeline.common import (
    AMBIGUOUS_TERMS,
    BRACKET_RE,
    CHARACTER_CARDS,
    NARRATOR_TO_CARD,
    ROOT,
    SSOT_PATH,
    WORK_DIR,
    read_json,
    resolve_src_and_out,
)

# 司书切换 / 内心潜入 / 叙述诡计触发词
TRICK_TRIGGERS = [
    ("潜入/内心世界", re.compile(r"ダイブ|ココロスフィア|ココロゲート|心の?世界|司書|クラン")),
    ("新司书/里人格特征词", re.compile(r"百鶴|白烏|リヴォルカ|四十九夜|家畜|月神楽|アスタシア|シンギュラリティ|エヴェレット|マルザンナ")),
    ("Meta/演出指令", re.compile(r"<meta\b|NOT DEVELOPED|フェノメノン|トライナリー")),
]

# 土佐腔特征词（用于提示雅的台词何时需要落桂柳话）
TOSA_RE = re.compile(r"ぜよ|ぞね|やき|きね|ちゅう|ちょる|しゆう|ちゃる|なんぞ|わからん|判らん|ほな|ほんだら|ほんで|まっこと|ちくっと|すまん|えいよ|えいね|ちや")


def prescan_file(src_path: Path, ssot: dict, out_md: Path | None = None) -> Path:
    data = read_json(src_path)
    entries = data.get("entry", [])
    info = data.get("info", {}) or {}
    terms: dict[str, dict] = ssot.get("terms", {})

    # 收集全文用于术语命中（按长度降序，避免短词淹没长词）
    all_texts = [
        str(info.get("title", "")),
        str(info.get("sub_title", "")),
        *(str(e.get("text", "")) for e in entries),
        *(str(e.get("narrator", "")) for e in entries),
    ]
    joined = "\n".join(all_texts)

    # 1. 命中的专名（限制在合理数量内，只保留本话真正用到的）
    hit_terms: list[tuple[str, str, str]] = []
    for jp in sorted(terms.keys(), key=len, reverse=True):
        if len(jp) <= 1:
            continue
        if jp in joined:
            t = terms[jp]
            hit_terms.append((jp, t["zh"], t["source"]))

    # 2. 方括号专名链接扫描（找出未入库的链接）
    bracket_links: set[str] = set()
    for t in all_texts:
        for m in BRACKET_RE.findall(t):
            bracket_links.add(m.strip())
    unregistered_links = sorted(b for b in bracket_links if b not in terms)

    # 3. 命中的歧义词
    hit_ambiguous = [(k, v) for k, v in AMBIGUOUS_TERMS.items() if k in joined]

    # 4. 出场说话人 & 角色卡裁剪
    alias_narr_re = re.compile(r"(？|\?|新司書|新司书|謎の|正体|誰か|黒衣|覆面)")
    narrators: list[str] = []
    alias_narrators: list[str] = []
    seen_narr = set()
    active_cards: list[str] = []
    seen_cards = set()
    for e in entries:
        nar = str(e.get("narrator", "")).strip()
        if nar and nar not in seen_narr:
            seen_narr.add(nar)
            narrators.append(nar)
            if alias_narr_re.search(nar):
                alias_narrators.append(nar)
            card_key = NARRATOR_TO_CARD.get(nar)
            if card_key and card_key not in seen_cards:
                seen_cards.add(card_key)
                active_cards.append(card_key)

    # 5. 叙述诡计 / 场景切换 / 雅方言标记扫描
    trick_hits: list[str] = []
    tosa_indices: list[int] = []
    for idx, e in enumerate(entries):
        txt = str(e.get("text", ""))
        loc = str(e.get("location", ""))
        nar = str(e.get("narrator", "")).strip()
        for label, pat in TRICK_TRIGGERS:
            m = pat.search(txt)
            if m:
                preview = txt.replace("\n", " ")[:40]
                trick_hits.append(f"- `#{idx}` (`{loc}`) [{nar or '旁白'}] **{label}** 命中 `{m.group(0)}`: `{preview}`")
        if nar in ("みやび", "恋ヶ崎みやび", "コイガサキ") and TOSA_RE.search(txt):
            tosa_indices.append(idx)

    # 生成 Context Pack Markdown
    rel = src_path.relative_to(ROOT) if src_path.is_relative_to(ROOT) else src_path.name
    lines: list[str] = [
        f"# Context Pack: `{rel}`",
        "",
        f"- **Type**: `{data.get('type', '')}` | **cid**: `{info.get('cid', '')}` | **Entries**: `{len(entries)}`",
        f"- **Title**: `{info.get('title', '')}` / `{info.get('sub_title', '')}`",
        f"- **出场说话人**: {', '.join(f'`{n}`' for n in narrators) if narrators else '无'}",
        "",
    ]

    if alias_narrators:
        lines.extend([
            "## 🎭 匿名 / 阶段性头衔核对预警",
            f"> 本话出现匿名或阶段性头衔：{', '.join(f'`{n}`' for n in alias_narrators)}。翻译与更新随读笔记前，**必须先对照随读笔记第 1 栏（长期关键锚点）与第 3 栏（已有口吻卡）**，比对立场、自称、称呼与语气，必要时用 `rg` 检索前文已译 JSON；若属同一角色换头衔（如 `？？？` → `〇〇の新司書` → 真名），须在笔记中合并关联并注明演变脉络，严禁拆成两条独立人设！",
            "",
        ])

    if trick_hits:
        lines.extend([
            "## ⚠️ 叙述诡计 / 场景切换预警",
            "> 若剧情从现实/WAVE切入内心世界，**`narrator` 仍可能顶着女主角名字，但实际说话人已变为司书**。请按司书口吻翻译，**严禁修改 `narrator_zh`**！",
            "",
            *trick_hits[:30],
            "",
        ])
        if len(trick_hits) > 30:
            lines.append(f"*(其余 {len(trick_hits) - 30} 条省略)*\n")

    if tosa_indices:
        lines.extend([
            "## 🗣️ 恋之崎雅 · 桂柳话触发条目",
            f"以下条目含土佐腔标记，需落桂柳话（其余标准语/技术句请收干净）：`{', '.join(f'#{i}' for i in tosa_indices)}`",
            "",
        ])

    if active_cards:
        lines.append("## 🎭 本话出场角色口吻卡")
        for ck in active_cards:
            lines.append(f"- {CHARACTER_CARDS[ck]}")
        lines.append("")

    if hit_ambiguous:
        lines.append("## 🔍 本话命中的语境歧义词")
        for k, note in hit_ambiguous:
            lines.append(f"- `{k}`: {note}")
        lines.append("")

    if unregistered_links:
        lines.append("## 🆕 未收录的 `[专名]` 方括号链接（需人工确认或打 `[?]`）")
        lines.append(", ".join(f"`[{u}]`" for u in unregistered_links))
        lines.append("")

    lines.append(f"## 📖 本话迷你专名表（共命中 {len(hit_terms)} 条）")
    if hit_terms:
        lines.append("| 原文 | 译文 | 来源 |")
        lines.append("| --- | --- | --- |")
        for jp, zh, src in hit_terms[:80]:
            lines.append(f"| `{jp}` | {zh} | {src} |")
        if len(hit_terms) > 80:
            lines.append(f"\n*(共 {len(hit_terms)} 条，此处仅展示前 80 条)*")
    else:
        lines.append("*(无命中词条)*")

    if out_md is None:
        safe_name = str(rel).replace("\\", "__").replace("/", "__")
        out_md = WORK_DIR / f"{safe_name}.context.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_md


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-scan source JSON and build Context Pack")
    parser.add_argument("files", nargs="+", help="Source JSON file(s) or glob relative to workspace root")
    args = parser.parse_args()

    if not SSOT_PATH.exists():
        raise SystemExit("ssot_glossary.json not found. Run `python -m pipeline.build_glossary` first.")
    ssot = read_json(SSOT_PATH)

    targets: list[Path] = []
    for pattern in args.files:
        p = Path(pattern)
        if p.exists() and p.is_file():
            src, _ = resolve_src_and_out(str(p))
            targets.append(src)
        else:
            targets.extend(sorted(ROOT.glob(pattern)))

    if not targets:
        raise SystemExit("No matching source files found.")

    for src in targets:
        out_md = prescan_file(src, ssot)
        print(f"Generated context pack: {out_md}")


if __name__ == "__main__":
    main()
