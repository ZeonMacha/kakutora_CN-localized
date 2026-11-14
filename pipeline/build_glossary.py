# -*- coding: utf-8 -*-
"""Stage 0: Merge 【翻译】/专名/*.json + STYLE_OVERRIDES into ssot_glossary.json."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from pipeline.common import (
    AMBIGUOUS_TERMS,
    GLOSSARY_DIR,
    SSOT_PATH,
    STYLE_OVERRIDES,
    read_json,
    write_json,
)


def _normalize_zh(zh: str) -> str:
    zh = zh.strip()
    # 统一旧表常见异写
    if zh == "埃弗雷特":
        return "艾弗雷特"
    if zh == "升华白乌":
        return "白鸦"
    return zh


def build_glossary(out_path: Path = SSOT_PATH) -> dict:
    """Collect terms from 【翻译】/专名/*.json and apply STYLE_OVERRIDES."""
    terms: dict[str, dict] = {}
    conflicts: list[dict] = []

    def add_term(jp: str, zh: str, source: str, note: str = "") -> None:
        jp = jp.strip()
        zh = _normalize_zh(zh)
        if not jp or not zh:
            return
        if jp in STYLE_OVERRIDES:
            # 高优先级规则直接覆盖
            zh = STYLE_OVERRIDES[jp]
        if jp in terms:
            prev = terms[jp]
            if prev["zh"] != zh:
                conflicts.append({
                    "jp": jp,
                    "kept": prev["zh"],
                    "kept_from": prev["source"],
                    "ignored": zh,
                    "ignored_from": source,
                })
            elif note and not prev.get("note"):
                prev["note"] = note
            return
        terms[jp] = {"zh": zh, "source": source, "note": note}

    # 1. 先注入 STYLE_OVERRIDES，确保最高优先级
    for jp, zh in STYLE_OVERRIDES.items():
        add_term(jp, zh, "文风.md")

    # 2. 按可信度顺序加载 【翻译】/专名/*.json
    priority_files = [
        ("角色名.json", "名称", "中文", ""),
        ("专名.json", "日语原文", "中文翻译", "释义中文参考"),
        ("Curan总表.json", "名字", "中文翻译", "注释"),
        ("技能.json", "名称", "中文", ""),
        ("服装.json", "名称", "中文", ""),
        ("道具.json", "名称", "中文", ""),
        ("Episode标题.json", "名称", "中文", ""),
        ("Special标题.json", "名称", "中文", ""),
        ("主线标题.json", "名称", "中文", ""),
        ("主线动画标题.json", "名称", "中文", ""),
        ("活动标题.json", "名称", "中文", ""),
        ("栏目标题.json", "名称", "中文", ""),
    ]

    for fname, jp_k, zh_k, note_k in priority_files:
        fpath = GLOSSARY_DIR / fname
        if not fpath.exists():
            continue
        data = read_json(fpath)
        rows = data.get("rows", []) if isinstance(data, dict) else data
        for row in rows:
            if not isinstance(row, dict):
                continue
            jp = str(row.get(jp_k, "") or "")
            zh = str(row.get(zh_k, "") or "")
            note = str(row.get(note_k, "") or "").strip() if note_k else ""
            add_term(jp, zh, fname, note)

    # 3. 加载 对照.json (list of {jp, zh})
    duizhao = GLOSSARY_DIR / "对照.json"
    if duizhao.exists():
        for row in read_json(duizhao):
            if isinstance(row, dict):
                add_term(str(row.get("jp", "")), str(row.get("zh", "")), "对照.json")

    # 4. 统计来源分布
    by_source: dict[str, int] = defaultdict(int)
    for info in terms.values():
        by_source[info["source"]] += 1

    payload = {
        "meta": {
            "total_terms": len(terms),
            "conflict_count": len(conflicts),
            "by_source": dict(by_source),
        },
        "terms": terms,
        "ambiguous": AMBIGUOUS_TERMS,
        "conflicts": conflicts,
    }
    write_json(out_path, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SSOT glossary from 【翻译】/专名")
    parser.add_argument("--out", type=Path, default=SSOT_PATH, help="Output JSON path")
    args = parser.parse_args()
    res = build_glossary(args.out)
    meta = res["meta"]
    print(f"SSOT glossary built: {args.out}")
    print(f"  Total terms : {meta['total_terms']}")
    print(f"  Conflicts   : {meta['conflict_count']}")
    for src, cnt in meta["by_source"].items():
        print(f"    - {src}: {cnt}")


if __name__ == "__main__":
    main()
