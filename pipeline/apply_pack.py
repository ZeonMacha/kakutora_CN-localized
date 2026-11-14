# -*- coding: utf-8 -*-
"""Stage 3: Safely apply a lightweight translation pack onto a source JSON and lint it."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.common import SSOT_PATH, read_json, resolve_src_and_out, write_json
from pipeline.lint import lint_file


def apply_pack(pack_path: Path, run_lint: bool = True) -> Path:
    pack = read_json(pack_path)
    file_ref = pack["file"]
    src_path, out_path = resolve_src_and_out(file_ref)
    if not src_path.exists():
        raise SystemExit(f"Source file not found: {src_path}")

    src = read_json(src_path)
    out = out_path.exists() and read_json(out_path) or src

    # 更新标题
    if "info" not in out or not isinstance(out["info"], dict):
        out["info"] = {}
    for k in ("title_zh", "sub_title_zh"):
        if k in pack and pack[k] is not None:
            out["info"][k] = pack[k]

    entries = out.get("entry", [])

    # 支持两种轻量格式：1) {"zhs": [...], "narrators_zh": [...]} 2) {"entries": [{"index": i, "zh": ..., "narrator_zh": ...}]}
    if "zhs" in pack:
        zhs = pack["zhs"]
        if len(zhs) != len(entries):
            raise SystemExit(f"Length mismatch: zhs={len(zhs)} vs entry={len(entries)}")
        nars = pack.get("narrators_zh")
        for i, zh in enumerate(zhs):
            entries[i]["zh"] = zh
            if nars is not None:
                entries[i]["narrator_zh"] = nars[i]
            elif "narrator_zh" not in entries[i]:
                entries[i]["narrator_zh"] = entries[i].get("narrator", "")
    elif "entries" in pack:
        for item in pack["entries"]:
            idx = int(item["index"])
            if not (0 <= idx < len(entries)):
                raise SystemExit(f"Index out of range: {idx}")
            if "zh" in item:
                entries[idx]["zh"] = item["zh"]
            if "narrator_zh" in item:
                entries[idx]["narrator_zh"] = item["narrator_zh"]
    else:
        raise SystemExit("Pack must contain either `zhs` or `entries`.")

    write_json(out_path, out)
    print(f"Applied translation -> {out_path}")

    if run_lint and SSOT_PATH.exists():
        ssot = read_json(SSOT_PATH)
        issues = lint_file(src_path, out_path, ssot)
        errs = [i for i in issues if i.level == "ERROR"]
        warns = [i for i in issues if i.level == "WARN"]
        qs = [i for i in issues if i.level == "QUESTION"]
        print(f"Auto-lint: ERROR={len(errs)} WARN={len(warns)} [?]={len(qs)}")
        for it in issues[:20]:
            loc = f"#{it.index}" if it.index is not None else "INFO"
            print(f"  {it.level:<8} {loc:<6} {it.code}: {it.message}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply translation pack to source JSON")
    parser.add_argument("pack", type=Path, help="Path to translation pack JSON")
    parser.add_argument("--no-lint", action="store_true", help="Skip auto-lint after applying")
    args = parser.parse_args()
    apply_pack(args.pack, run_lint=not args.no_lint)


if __name__ == "__main__":
    main()
