# -*- coding: utf-8 -*-
"""Assembly pipeline: align a single translated story/pack onto multiple target JSONs.

Typical usage:
    # Auto-align anime_01_05 onto anime_02_05, anime_03_05, anime_04_05 (packs only)
    python -m pipeline.assemble stories/anime_01_05.json

    # Auto-align and immediately apply + lint into 【翻译】/stories/
    python -m pipeline.assemble "stories/anime_01_*.json" --apply

    # Align from a translation pack directly onto explicit targets
    python -m pipeline.assemble pipeline/work/pack_anime_01_05.json --apply
"""

from __future__ import annotations

import argparse
import difflib
import glob
import re
from pathlib import Path
from typing import Any

from pipeline.apply_pack import apply_pack
from pipeline.common import ROOT, TR_ROOT, WORK_DIR, read_json, resolve_src_and_out, write_json

ANIME_ROUTE_RE = re.compile(r"^(anime_)01((?:_\d+)?\.json)$")


def _loc_type(location: str) -> str:
    return location.split("/", 1)[1] if "/" in location else location


def load_translated_source(input_path: Path) -> tuple[Path, dict[str, Any], dict[str, str]]:
    """Load source Japanese entries + zh translations from a pack or translated JSON."""
    raw = read_json(input_path)

    # Case 1: Translation pack JSON (has "file" and "entries" or "zhs")
    if "file" in raw and ("entries" in raw or "zhs" in raw):
        src_path, _ = resolve_src_and_out(raw["file"])
        src_data = read_json(src_path)
        entries = src_data.get("entry", [])
        trans_map: dict[int, tuple[str, str]] = {}
        if "zhs" in raw:
            nars = raw.get("narrators_zh")
            for i, zh in enumerate(raw["zhs"]):
                nar_zh = nars[i] if nars is not None else entries[i].get("narrator", "")
                trans_map[i] = (zh, nar_zh)
        else:
            for item in raw["entries"]:
                idx = int(item["index"])
                zh = item.get("zh", "")
                nar_zh = item.get("narrator_zh", entries[idx].get("narrator", ""))
                trans_map[idx] = (zh, nar_zh)

        merged_entries = []
        for i, e in enumerate(entries):
            item = dict(e)
            if i in trans_map:
                item["zh"], item["narrator_zh"] = trans_map[i]
            merged_entries.append(item)
        src_data["entry"] = merged_entries
        titles = {
            k: raw[k] for k in ("title_zh", "sub_title_zh") if k in raw and raw[k] is not None
        }
        return src_path, src_data, titles

    # Case 2: Source path or translated 【翻译】/stories/... path
    src_path, out_path = resolve_src_and_out(str(input_path))
    if not out_path.exists():
        raise SystemExit(f"Translated file not found: {out_path}")
    out_data = read_json(out_path)
    info = out_data.get("info", {})
    titles = {
        k: info[k] for k in ("title_zh", "sub_title_zh") if k in info and info[k] is not None
    }
    return src_path, out_data, titles


def infer_anime_targets(src_path: Path, include_self: bool = False) -> list[Path]:
    """Infer anime_02..04 sibling targets from an anime_01*.json path."""
    m = ANIME_ROUTE_RE.match(src_path.name)
    if not m:
        return []
    prefix, suffix = m.group(1), m.group(2)
    routes = ["01", "02", "03", "04"] if include_self else ["02", "03", "04"]
    targets = []
    for r in routes:
        cand = src_path.parent / f"{prefix}{r}{suffix}"
        if cand.exists():
            targets.append(cand)
    return targets


def align_entries(
    src_entries: list[dict[str, Any]],
    tgt_entries: list[dict[str, Any]],
    fuzzy_threshold: float = 0.95,
) -> tuple[list[dict[str, Any]], list[tuple[int, int, float, str, str]], list[tuple[int, str]]]:
    """Align translated src_entries onto tgt_entries.

    Returns:
        pack_entries: list of {"index": j, "zh": ..., "narrator_zh": ...}
        fuzzy_matches: list of (tgt_idx, src_idx, ratio, src_text, tgt_text)
        unmatched: list of (tgt_idx, tgt_text)
    """
    src_texts = [e.get("text", "") for e in src_entries]
    tgt_texts = [e.get("text", "") for e in tgt_entries]

    # Map tgt_idx -> (src_idx, mode, ratio)
    mapping: dict[int, tuple[int, str, float]] = {}
    used_src: set[int] = set()

    # Pass 1: SequenceMatcher equal blocks (preserves order for duplicate lines)
    sm = difflib.SequenceMatcher(None, src_texts, tgt_texts, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(j2 - j1):
                si, tj = i1 + k, j1 + k
                if "zh" in src_entries[si]:
                    mapping[tj] = (si, "seq", 1.0)
                    used_src.add(si)

    # Build lookup indices for Pass 2
    by_loc_nar_txt: dict[tuple[str, str, str], list[int]] = {}
    by_nar_txt: dict[tuple[str, str], list[int]] = {}
    by_txt: dict[str, list[int]] = {}
    for i, e in enumerate(src_entries):
        if "zh" not in e:
            continue
        t = e.get("text", "")
        n = e.get("narrator", "")
        lt = _loc_type(e.get("location", ""))
        by_loc_nar_txt.setdefault((lt, n, t), []).append(i)
        by_nar_txt.setdefault((n, t), []).append(i)
        by_txt.setdefault(t, []).append(i)

    def _pick(cands: list[int] | None) -> int | None:
        if not cands:
            return None
        for idx in cands:
            if idx not in used_src:
                return idx
        return cands[0]

    # Pass 2: Exact key fallback for reordered/non-equal entries
    for j, te in enumerate(tgt_entries):
        if j in mapping:
            continue
        t = te.get("text", "")
        n = te.get("narrator", "")
        lt = _loc_type(te.get("location", ""))
        si = (
            _pick(by_loc_nar_txt.get((lt, n, t)))
            or _pick(by_nar_txt.get((n, t)))
            or _pick(by_txt.get(t))
        )
        if si is not None:
            mapping[j] = (si, "exact", 1.0)
            used_src.add(si)

    # Pass 3: Fuzzy matching for minor line-ending/particle differences
    if fuzzy_threshold < 1.0:
        for j, te in enumerate(tgt_entries):
            if j in mapping:
                continue
            t = te.get("text", "")
            n = te.get("narrator", "")
            if not t.strip():
                continue
            best_ratio = 0.0
            best_si = -1
            for i, se in enumerate(src_entries):
                if "zh" not in se:
                    continue
                st = se.get("text", "")
                if abs(len(st) - len(t)) > max(10, int(len(t) * 0.4)):
                    continue
                r = difflib.SequenceMatcher(None, st, t).ratio()
                if se.get("narrator", "") == n:
                    r += 0.01  # slight preference for same narrator
                if r > best_ratio:
                    best_ratio = r
                    best_si = i
            if best_si >= 0 and best_ratio >= fuzzy_threshold:
                mapping[j] = (best_si, "fuzzy", min(best_ratio, 1.0))
                used_src.add(best_si)

    pack_entries: list[dict[str, Any]] = []
    fuzzy_matches: list[tuple[int, int, float, str, str]] = []
    unmatched: list[tuple[int, str]] = []

    for j, te in enumerate(tgt_entries):
        if j not in mapping:
            unmatched.append((j, te.get("text", "")))
            continue
        si, mode, ratio = mapping[j]
        se = src_entries[si]
        tgt_nar = te.get("narrator", "")

        if tgt_nar == "":
            nar_zh = ""
        elif tgt_nar.startswith("Dialog_chapter_"):
            nar_zh = tgt_nar
        else:
            nar_zh = se.get("narrator_zh", tgt_nar)

        pack_entries.append({
            "index": j,
            "zh": se["zh"],
            "narrator_zh": nar_zh,
        })
        if mode == "fuzzy":
            fuzzy_matches.append((j, si, ratio, se.get("text", ""), te.get("text", "")))

    return pack_entries, fuzzy_matches, unmatched


def assemble_one(
    input_path: Path,
    target_paths: list[Path] | None = None,
    apply: bool = False,
    fuzzy_threshold: float = 0.95,
    overrides_path: Path | None = None,
) -> list[Path]:
    src_path, src_data, titles = load_translated_source(input_path)
    is_pack = input_path.resolve().is_relative_to(WORK_DIR.resolve()) or "pack_" in input_path.name

    if not target_paths:
        target_paths = infer_anime_targets(src_path, include_self=is_pack)
    if not target_paths:
        raise SystemExit(f"No target files specified or inferred for {src_path}")

    overrides: dict[str, dict[str, Any]] = {}
    if overrides_path and overrides_path.exists():
        overrides = read_json(overrides_path)

    src_entries = src_data.get("entry", [])
    generated_packs: list[Path] = []

    for tgt_path in target_paths:
        tgt_data = read_json(tgt_path)
        tgt_entries = tgt_data.get("entry", [])
        pack_entries, fuzzy_matches, unmatched = align_entries(
            src_entries, tgt_entries, fuzzy_threshold=fuzzy_threshold
        )

        # Apply optional per-file overrides
        file_ov = overrides.get(tgt_path.name, {})
        if file_ov:
            by_idx = {item["index"]: item for item in pack_entries}
            for idx_str, patch in file_ov.items():
                idx = int(idx_str)
                if idx in by_idx:
                    by_idx[idx].update(patch)
                else:
                    pack_entries.append({"index": idx, **patch})
                    unmatched = [(u_idx, u_txt) for u_idx, u_txt in unmatched if u_idx != idx]
            pack_entries.sort(key=lambda x: x["index"])

        rel_file = tgt_path.resolve().relative_to(ROOT.resolve()).as_posix()
        pack: dict[str, Any] = {"file": rel_file}
        pack.update(titles)
        pack["entries"] = pack_entries

        WORK_DIR.mkdir(parents=True, exist_ok=True)
        pack_path = WORK_DIR / f"pack_{tgt_path.stem}.json"
        write_json(pack_path, pack)
        generated_packs.append(pack_path)

        total = len(tgt_entries)
        matched = len(pack_entries)
        exact_cnt = matched - len(fuzzy_matches)
        print(
            f"[{tgt_path.name}] aligned {matched}/{total} "
            f"(exact={exact_cnt}, fuzzy={len(fuzzy_matches)}, unmatched={len(unmatched)}) "
            f"-> {pack_path.relative_to(ROOT).as_posix()}"
        )
        for j, si, ratio, st, tt in fuzzy_matches:
            print(f"  [FUZZY #{j}<-#{si} ({ratio:.2f})] {st!r} => {tt!r}")
        for j, tt in unmatched[:5]:
            print(f"  [UNMATCHED #{j}] {tt!r}")
        if len(unmatched) > 5:
            print(f"  ... (+{len(unmatched) - 5} more unmatched entries)")

        if apply:
            apply_pack(pack_path, run_lint=True)

    return generated_packs


def _expand_inputs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if hits:
            paths.extend(Path(h) for h in hits)
        else:
            paths.append(Path(pat))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Align a single translated story/pack onto multiple target JSONs."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Source translated JSON(s), source story JSON(s), or pack JSON(s) (glob supported)",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        default=None,
        help="Explicit target story JSON(s) (glob supported). Auto-inferred for anime_01*.json if omitted.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Immediately apply generated packs to 【翻译】/stories/ and run lint",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.95,
        help="SequenceMatcher threshold for minor text diffs (default: 0.95; 1.0 disables)",
    )
    parser.add_argument(
        "--overrides",
        type=Path,
        default=None,
        help="Optional JSON file mapping target filename -> {index: {zh, narrator_zh}}",
    )
    args = parser.parse_args()

    input_paths = _expand_inputs(args.inputs)
    target_paths = _expand_inputs(args.targets) if args.targets else None

    for inp in input_paths:
        assemble_one(
            inp,
            target_paths=target_paths,
            apply=args.apply,
            fuzzy_threshold=args.fuzzy_threshold,
            overrides_path=args.overrides,
        )


if __name__ == "__main__":
    main()
