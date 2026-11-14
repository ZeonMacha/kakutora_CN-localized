# -*- coding: utf-8 -*-
"""Stage 4: Automated Linter for translated JSON files."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pipeline.common import (
    BRACKET_RE,
    GLOBAL_FORBIDDEN,
    KANA_RE,
    MIYABI_FORBIDDEN,
    ROOT,
    SSOT_PATH,
    TAG_RE,
    TR_ROOT,
    URL_RE,
    read_json,
    resolve_src_and_out,
)

NOW_RE = re.compile(r"\bnow\b", re.IGNORECASE)
PYON_ROM_RE = re.compile(r"\bpyon\b", re.IGNORECASE)


@dataclass
class Issue:
    level: str  # ERROR | WARN | QUESTION
    index: int | None
    code: str
    message: str


def lint_file(src_path: Path, out_path: Path, ssot: dict) -> list[Issue]:
    issues: list[Issue] = []
    if not src_path.exists():
        return [Issue("ERROR", None, "MISSING_SRC", f"Source file not found: {src_path}")]
    if not out_path.exists():
        return [Issue("ERROR", None, "MISSING_OUT", f"Translated file not found: {out_path}")]

    src = read_json(src_path)
    out = read_json(out_path)

    # 1. Info title check
    s_info = src.get("info", {}) or {}
    o_info = out.get("info", {}) or {}
    if s_info.get("title") and not o_info.get("title_zh"):
        issues.append(Issue("WARN", None, "MISSING_TITLE_ZH", "info.title_zh is empty"))
    if s_info.get("sub_title") and not o_info.get("sub_title_zh"):
        issues.append(Issue("WARN", None, "MISSING_SUBTITLE_ZH", "info.sub_title_zh is empty"))

    s_entries = src.get("entry", [])
    o_entries = out.get("entry", [])
    if len(s_entries) != len(o_entries):
        issues.append(Issue("ERROR", None, "ENTRY_COUNT", f"Entry count mismatch: src={len(s_entries)} out={len(o_entries)}"))
        return issues

    terms: dict[str, dict] = ssot.get("terms", {})

    for idx, (a, b) in enumerate(zip(s_entries, o_entries)):
        # 2. 原文字段不可篡改
        for k in ("location", "narrator", "text"):
            if a.get(k) != b.get(k):
                issues.append(Issue("ERROR", idx, "SRC_MUTATED", f"Field `{k}` modified"))

        text = str(a.get("text", ""))
        zh = str(b.get("zh", ""))
        nar = str(a.get("narrator", ""))
        nar_zh = str(b.get("narrator_zh", ""))

        # 3. narrator_zh 一致性
        if nar == "" and nar_zh != "":
            issues.append(Issue("ERROR", idx, "NARRATOR_NONEMPTY", f"narrator is empty but narrator_zh={nar_zh!r}"))
        elif nar != "" and nar_zh == "":
            issues.append(Issue("ERROR", idx, "NARRATOR_EMPTY", f"narrator={nar!r} but narrator_zh is empty"))

        # 4. 未译检查
        if text.strip() and not zh.strip():
            issues.append(Issue("ERROR", idx, "EMPTY_ZH", "zh is empty"))
            continue

        # 5. 换行符数量一致
        if text.count("\n") != zh.count("\n"):
            issues.append(Issue("ERROR", idx, "NEWLINE_MISMATCH", f"Newlines src={text.count(chr(10))} zh={zh.count(chr(10))}"))

        # 6. 标记/变量/URL 完整保留
        if Counter(TAG_RE.findall(text)) != Counter(TAG_RE.findall(zh)):
            issues.append(Issue("ERROR", idx, "TAG_MISMATCH", f"Tags/vars mismatch: src={TAG_RE.findall(text)} zh={TAG_RE.findall(zh)}"))
        if Counter(URL_RE.findall(text)) != Counter(URL_RE.findall(zh)):
            issues.append(Issue("ERROR", idx, "URL_MISMATCH", "URL modified or missing"))

        # 7. 方括号专名链接检查（排除校对标记 [?]）
        src_links = BRACKET_RE.findall(text)
        zh_links = BRACKET_RE.findall(zh.replace("[?]", ""))
        if len(src_links) != len(zh_links):
            issues.append(Issue("ERROR", idx, "BRACKET_COUNT", f"Bracket link count src={src_links} zh={zh_links}"))
        else:
            for sl, zl in zip(src_links, zh_links):
                sl_s = sl.strip()
                if sl_s in terms and terms[sl_s]["zh"] != zl.strip():
                    issues.append(Issue("ERROR", idx, "BRACKET_TERM", f"[{sl_s}] should be [{terms[sl_s]['zh']}], got [{zl}]"))

        # 8. 假名残留检查（原文中未原样出现的假名不得残留）
        for ch in zh:
            if KANA_RE.match(ch) and ch not in text:
                issues.append(Issue("ERROR", idx, "KANA_LEAK", f"Unexpected kana `{ch}` in zh: {zh[:40]}"))
                break

        # 9. 全局禁字
        for bad in GLOBAL_FORBIDDEN:
            if bad in zh:
                issues.append(Issue("ERROR", idx, "FORBIDDEN_WORD", f"Forbidden word `{bad}` in zh"))

        # 10. 雅桂柳话禁用词
        if nar.strip() in ("みやび", "恋ヶ崎みやび", "コイガサキ"):
            for bad in MIYABI_FORBIDDEN:
                if bad in zh:
                    issues.append(Issue("ERROR", idx, "MIYABI_FORBIDDEN", f"Non-Guiliu word `{bad}` in Miyabi line"))

        # 11. 神乐 pyon 口癖防滥用
        if PYON_ROM_RE.search(zh) and "ぴょん" not in text.replace("ぴょんこ", ""):
            issues.append(Issue("ERROR", idx, "PYON_MISUSE", "`pyon` used without `ぴょん` in source"))

        # 12. なう -> now 残留
        if "なう" in text and NOW_RE.search(zh):
            issues.append(Issue("WARN", idx, "NOW_LEAK", "`なう` translated with literal `now`"))

        # 13. ジュエル -> 宝石 误用提示
        if "ジュエル" in text and "宝石" in zh and "珠宝" not in zh:
            issues.append(Issue("WARN", idx, "JEWEL_CHECK", "`ジュエル` rendered as `宝石` (confirm not currency `珠宝`)"))

        # 14. 敬称「您」检查
        if "您" in zh and nar.strip() in ("つばめ", "アーヤ", "ガブリエラ", "みやび", "神楽", "千羽鶴"):
            issues.append(Issue("WARN", idx, "POLITE_NIN", "Used `您` in main character dialogue (文风.md requires `你`)"))

        # 15. [?] 待校对标记汇总
        if "[?]" in zh:
            issues.append(Issue("QUESTION", idx, "NEEDS_REVIEW", zh.replace("\n", " ")[:80]))

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint translated JSON files against 文风.md & SSOT glossary")
    parser.add_argument("targets", nargs="+", help="Translated file(s) or glob (under 【翻译】/ or relative)")
    parser.add_argument("--errors-only", action="store_true", help="Only print ERRORs")
    args = parser.parse_args()

    if not SSOT_PATH.exists():
        raise SystemExit("ssot_glossary.json not found. Run `python -m pipeline.build_glossary` first.")
    ssot = read_json(SSOT_PATH)

    pairs: list[tuple[Path, Path]] = []
    for pat in args.targets:
        p = Path(pat)
        if p.exists() and p.is_file():
            pairs.append(resolve_src_and_out(str(p)))
        else:
            for matched in sorted(ROOT.glob(pat)):
                if matched.is_file():
                    pairs.append(resolve_src_and_out(str(matched)))

    if not pairs:
        raise SystemExit("No matching files found.")

    total_err = total_warn = total_q = 0
    for src, out in pairs:
        issues = lint_file(src, out, ssot)
        errs = [i for i in issues if i.level == "ERROR"]
        warns = [i for i in issues if i.level == "WARN"]
        qs = [i for i in issues if i.level == "QUESTION"]
        total_err += len(errs)
        total_warn += len(warns)
        total_q += len(qs)

        rel = out.relative_to(TR_ROOT) if out.is_relative_to(TR_ROOT) else out
        if issues:
            print(f"[{rel}] ERROR={len(errs)} WARN={len(warns)} [?]={len(qs)}")
            for it in issues:
                if args.errors_only and it.level != "ERROR":
                    continue
                loc = f"#{it.index}" if it.index is not None else "INFO"
                print(f"  {it.level:<8} {loc:<6} {it.code}: {it.message}")
        else:
            print(f"[{rel}] OK")

    print(f"\nSummary: files={len(pairs)} ERROR={total_err} WARN={total_warn} [?]={total_q}")
    if total_err > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
