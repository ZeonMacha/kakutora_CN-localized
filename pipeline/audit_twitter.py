# -*- coding: utf-8 -*-
"""Dedicated quality auditor for Twitter archive translations under 【翻译】/web/."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from pipeline.common import ROOT, SSOT_PATH, TR_ROOT, read_json
from pipeline.lint import lint_file

HEROINE_NARRATOR_MAP: dict[str, str] = {
    "逢瀬つばめ": "逢濑燕",
    "あやみ": "绫水",
    "Garbiela": "加布里埃拉",
    "コイガサキ": "恋之崎",
    "神": "神",
}

TW_FILES = [
    "profiles.json",
    "tsubame_ohse.json",
    "ayami_kunimasa.json",
    "garbiela_lotty.json",
    "miyabi_koikoi.json",
    "kagura_pyonko.json",
    "replies.json",
    "twitter_archive__search.json",
]

AT_RE = re.compile(r"@[A-Za-z0-9_]+")
# 2+ full-width actual Hiragana/Katakana letters (excludes ・ U+30FB, ゜ U+309C, ー U+30FC, ヽ U+30FD kaomoji marks)
KANA2_RE = re.compile(r"[\u3041-\u3096\u30a1-\u30fa]{2,}")
HONORIFIC_RE = re.compile(
    r"(?:逢濑燕|逢濑|国政绫水|国政|绫水|加布里埃拉|加布|恋之崎雅|恋之崎|卯月神乐|卯月|神乐|(?<![小大])燕|(?<![优高])雅)(?:小姐|酱|桑)|(?<!水陆两用)小(?:加布|燕|神乐)"
)

# Exact entries or substrings allowed to keep kana (ciphers, mojibake, intentional meta)
ALLOWED_KANA_SUBSTRINGS = {
    "ヒトヨヒトヨニヒトミゴロ",
    "テヘペロ",
    "ノシ",
    "ワロス",
    "オワタ",
}

# Twitter-specific canonical terms (enforced only on Twitter archive files)
TW_TERM_GUARDS: tuple[tuple[str, str], ...] = (
    ("プラツキ", "普拉茨基"),
    ("カプドラ", "卡普多拉"),
    ("トリプルメルティーズ", "三重融化"),
    ("こいがさ子", "小恋恋子"),
    ("エルガリア", "艾尔加利亚"),
)


def audit_twitter(files: list[str] | None = None, verbose: bool = False) -> int:
    ssot = read_json(SSOT_PATH)
    targets = files or TW_FILES

    # Collect all passerby display names so if quoted in text we don't false-positive on kana
    rep_src = read_json(ROOT / "web" / "replies.json")["entry"]
    passerby_names = {
        e["narrator"].strip()
        for e in rep_src
        if e["narrator"].strip() and e["narrator"].strip() not in HEROINE_NARRATOR_MAP
    }

    total_errors = 0
    total_warns = 0
    dup_zh_map: dict[str, set[tuple[str, int, str]]] = defaultdict(set)

    for fname in targets:
        src_path = ROOT / "web" / fname
        out_path = TR_ROOT / "web" / fname
        if not out_path.exists():
            print(f"[web/{fname}] ERROR: missing translated file")
            total_errors += 1
            continue

        # 1. Run standard pipeline.lint
        lint_issues = lint_file(src_path, out_path, ssot)
        l_err = [i for i in lint_issues if i.level == "ERROR"]
        l_warn = [i for i in lint_issues if i.level == "WARN"]
        l_q = [i for i in lint_issues if i.level == "QUESTION"]

        src = read_json(src_path)["entry"]
        out = read_json(out_path)["entry"]

        tw_err: list[str] = []
        tw_warn: list[str] = []

        for idx, (se, te) in enumerate(zip(src, out)):
            nar = se.get("narrator", "")
            nar_zh = te.get("narrator_zh", "")
            txt = se.get("text", "")
            zh = te.get("zh", "")

            # 2. Strict narrator_zh lock
            if nar in HEROINE_NARRATOR_MAP:
                exp = HEROINE_NARRATOR_MAP[nar]
                if nar_zh != exp:
                    tw_err.append(f"#{idx} NARRATOR_HEROINE: {nar!r} expected {exp!r}, got {nar_zh!r}")
            elif nar != "":
                if nar_zh != nar:
                    tw_err.append(f"#{idx} NARRATOR_PASSERBY: {nar!r} mutated to {nar_zh!r}")

            if not zh.strip():
                continue

            # 3. @handle multiset lock
            if Counter(AT_RE.findall(txt)) != Counter(AT_RE.findall(zh)):
                tw_err.append(f"#{idx} HANDLE_MISMATCH: src={AT_RE.findall(txt)} zh={AT_RE.findall(zh)}")

            # 4. Standard hashtag check
            if "#トライナリー" in txt and "#三重奏" not in zh:
                tw_err.append(f"#{idx} HASHTAG_TRINARY: missing `#三重奏`")
            if "＃トライナリー" in txt and "＃三重奏" not in zh:
                tw_err.append(f"#{idx} HASHTAG_TRINARY_FW: missing `＃三重奏`")
            if "#ピクトラ" in txt and "#Pic-Tri" not in zh:
                tw_err.append(f"#{idx} HASHTAG_PICTRI: missing `#Pic-Tri`")
            if "＃ピクトラ" in txt and "＃Pic-Tri" not in zh:
                tw_err.append(f"#{idx} HASHTAG_PICTRI_FW: missing `＃Pic-Tri`")

            # 5. Twitter canonical term guards
            flat_txt = txt.replace("\n", "")
            for jp, cn in TW_TERM_GUARDS:
                if jp in flat_txt and cn not in zh:
                    tw_err.append(f"#{idx} TW_TERM: `{jp}` should be `{cn}`")

            # 6. Untranslated 2+ kana leak check (excluding mojibake entry #1149 and allowlist)
            if not (fname == "miyabi_koikoi.json" and idx == 1149):
                zh_clean = zh
                for a in ALLOWED_KANA_SUBSTRINGS:
                    zh_clean = zh_clean.replace(a, "")
                for pn in passerby_names:
                    if len(pn) >= 2 and pn in zh_clean:
                        zh_clean = zh_clean.replace(pn, "")
                m = KANA2_RE.search(zh_clean)
                if m:
                    tw_err.append(f"#{idx} KANA2_LEAK: `{m.group(0)}` in {zh[:60]!r}")

            # 7. Honorific regression warning/error
            hm = HONORIFIC_RE.search(zh)
            if hm:
                tw_warn.append(f"#{idx} HONORIFIC_CHECK: `{hm.group(0)}` in {zh[:60]!r}")

            # Track shared notices & exact duplicates across files
            if fname in ("tsubame_ohse.json", "ayami_kunimasa.json", "garbiela_lotty.json", "miyabi_koikoi.json", "kagura_pyonko.json"):
                if "NOTICE!" in txt or "自動送信" in txt or "【定期】" in txt or "【不定期定期】" in txt:
                    dup_zh_map[txt].add((fname, idx, zh))

        print(
            f"[web/{fname}] lint_ERR={len(l_err)} lint_WARN={len(l_warn)} [?]={len(l_q)} "
            f"| tw_ERR={len(tw_err)} tw_WARN={len(tw_warn)}"
        )
        if verbose or l_err or tw_err:
            for it in l_err[:15]:
                print(f"  LINT_ERR #{it.index} {it.code}: {it.message}")
            for msg in tw_err[:15]:
                print(f"  TW_ERR   {msg}")
        if verbose:
            for it in l_warn[:10]:
                print(f"  LINT_WRN #{it.index} {it.code}: {it.message}")
            for msg in tw_warn[:10]:
                print(f"  TW_WRN   {msg}")

        total_errors += len(l_err) + len(tw_err)
        total_warns += len(l_warn) + len(tw_warn)

    # 8. Cross-file shared broadcast / notice consistency check
    dup_err = 0
    for txt, entries in dup_zh_map.items():
        distinct_zhs = {z for _, _, z in entries}
        if len(distinct_zhs) > 1:
            dup_err += 1
            print(f"[CROSS_FILE_DUP_MISMATCH] src={txt[:60]!r} has {len(distinct_zhs)} variants:")
            for fn, idx, z in sorted(entries)[:5]:
                print(f"  - {fn}#{idx}: {z[:70]!r}")
    total_errors += dup_err

    print(f"\nTwitter Audit Summary: TOTAL_ERROR={total_errors} TOTAL_WARN={total_warns}")
    return 1 if total_errors > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Twitter archive translations")
    parser.add_argument("files", nargs="*", help="Optional specific filenames under web/")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show warnings too")
    args = parser.parse_args()
    raise SystemExit(audit_twitter(args.files or None, verbose=args.verbose))


if __name__ == "__main__":
    main()
