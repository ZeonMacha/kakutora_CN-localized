#!/usr/bin/env python3
"""Merge a CJK fallback into an existing font.

The script takes three command-line arguments:

    python merge_cjk_fallback.py INPUT1 INPUT2 OUTPUT

It removes every Unicode character in the CJK ranges below from INPUT1,
creating an in-memory "intermediate1" font, then adds every character from
INPUT2 that is missing from intermediate1 and writes OUTPUT.

Removed ranges (inclusive):
    U+2E80..U+2EFF, U+3400..U+4DFF, U+4E00..U+9FFF,
    U+F900..U+FAFF, U+20000..U+2FFFF, U+30000..U+3FFFF

The output keeps INPUT1's outlines for its remaining characters, names,
horizontal/vertical metrics and OpenType layout tables.  Missing characters
are copied from INPUT2 as CFF outlines.  INPUT2's OpenType layout tables are
not copied, because they describe glyphs that are not part of INPUT1's
layout system.

Both inputs must be CFF-flavoured OpenType fonts with the same unitsPerEm.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path

from fontTools import subset
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.timeTools import timestampNow
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont

CJK_RANGES = (
    (0x2E80, 0x2EFF),  # CJK Radicals Supplement
    (0x3400, 0x4DFF),  # CJK Unified Ideographs Extension A
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
    (0x20000, 0x2FFFF),  # CJK Unified Ideographs Extension B-F, compatibility supplement
    (0x30000, 0x3FFFF),  # CJK Unified Ideographs Extension G+
)

REQUIRED_TABLES = (
    "CFF ",
    "cmap",
    "head",
    "hhea",
    "hmtx",
    "maxp",
    "name",
    "OS/2",
    "post",
)

# Top-dict fields that are safe and useful to carry over to a name-keyed CFF.
CFF_INFO_KEYS = (
    "Notice",
    "FullName",
    "FamilyName",
    "Weight",
    "ItalicAngle",
    "isFixedPitch",
    "UnderlinePosition",
    "UnderlineThickness",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove CJK characters from INPUT1, supplement missing characters "
            "from INPUT2, and write a merged CFF OTF."
        )
    )
    parser.add_argument(
        "input1",
        metavar="INPUT1",
        type=Path,
        help="base font; its CJK characters are removed",
    )
    parser.add_argument(
        "input2",
        metavar="INPUT2",
        type=Path,
        help="fallback font supplying characters missing from INPUT1",
    )
    parser.add_argument(
        "output",
        metavar="OUTPUT",
        type=Path,
        help="merged CFF OTF to write",
    )
    return parser.parse_args()


def is_cjk(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in CJK_RANGES)


def get_unicode_cmap(font: TTFont, label: str) -> dict[int, str]:
    cmap = font.getBestCmap()
    if not cmap:
        raise ValueError(f"{label} has no usable Unicode cmap")
    return dict(cmap)


def make_intermediate1(font: TTFont, keep_codepoints: set[int]) -> dict[int, str]:
    """Subset INPUT1 to its non-CJK characters, in place.

    Keeping all layout features preserves INPUT1's GSUB/GPOS behaviour for the
    characters that remain.  The subsetter also drops glyphs that are not
    reachable from the retained characters/features.
    """
    options = subset.Options()
    options.layout_features = ["*"]
    options.layout_closure = True
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.name_legacy = True
    options.notdef_glyph = True
    options.notdef_outline = True
    options.recalc_bounds = False

    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=sorted(keep_codepoints))
    subsetter.subset(font)

    remaining = get_unicode_cmap(font, "intermediate1")
    missing = keep_codepoints.difference(remaining)
    if missing:
        sample = ", ".join(f"U+{cp:04X}" for cp in sorted(missing)[:8])
        raise RuntimeError(
            f"Subsetting INPUT1 unexpectedly removed {len(missing)} "
            f"non-CJK characters ({sample})"
        )
    extra = set(remaining).difference(keep_codepoints)
    if extra:
        sample = ", ".join(f"U+{cp:04X}" for cp in sorted(extra)[:8])
        raise RuntimeError(
            f"Subsetting INPUT1 left {len(extra)} unexpected characters "
            f"({sample})"
        )
    return remaining


def make_merge_plan(
    base: TTFont,
    source: TTFont,
    base_cmap: dict[int, str],
    source_cmap: dict[int, str],
) -> tuple[dict[int, str], list[str], dict[str, str], dict[int, str]]:
    """Return output cmap, glyph order, output->source glyph map, and additions."""
    missing = {
        cp: glyph_name
        for cp, glyph_name in source_cmap.items()
        if cp not in base_cmap
    }

    needed_source_glyphs = set(missing.values())
    base_order = list(base.getGlyphOrder())
    if not base_order or base_order[0] != ".notdef":
        raise RuntimeError("INPUT1 does not start with a .notdef glyph")

    used_names = set(base_order)
    source_names: dict[str, str] = {}
    source_order = list(source.getGlyphOrder())
    for gid, glyph_name in enumerate(source_order):
        if glyph_name not in needed_source_glyphs:
            continue
        candidate = f"s2.{glyph_name}"
        if candidate in used_names:
            candidate = f"s2.g{gid:05d}"
        while candidate in used_names:
            candidate += ".1"
        used_names.add(candidate)
        source_names[glyph_name] = candidate

    source_by_out = {out_name: src_name for src_name, out_name in source_names.items()}
    out_order = base_order + [
        source_names[glyph_name]
        for glyph_name in source_order
        if glyph_name in source_names
    ]
    if len(out_order) > 0xFFFF:
        raise RuntimeError(
            f"Merged font needs {len(out_order)} glyphs; the OpenType maximum is 65535"
        )
    if len(set(out_order)) != len(out_order):
        raise RuntimeError("Duplicate glyph names in merged glyph order")

    out_cmap = dict(base_cmap)
    for cp, source_glyph in missing.items():
        out_cmap[cp] = source_names[source_glyph]

    return out_cmap, out_order, source_by_out, missing


def make_charstrings_and_metrics(
    base: TTFont,
    source: TTFont,
    out_order: list[str],
    source_by_out: dict[str, str],
    include_vertical: bool,
    vorg_default: int,
) -> tuple[
    dict[str, object],
    dict[str, tuple[int, int]],
    dict[str, tuple[int, int]] | None,
    dict[str, int],
]:
    """Rebuild every output glyph as a standalone CFF charstring.

    The pens discard source hinting/subroutines but preserve outlines, widths
    and sidebearings.  Standalone charstrings let us combine two CID-keyed CFF
    fonts without trying to merge incompatible FDArray/Subrs data.
    """
    base_gs = base.getGlyphSet()
    source_gs = source.getGlyphSet()
    base_hmtx = base["hmtx"].metrics
    source_hmtx = source["hmtx"].metrics
    base_vmtx = base["vmtx"].metrics if include_vertical else None
    source_vmtx = source["vmtx"].metrics if include_vertical else None
    base_vorg = base["VORG"] if "VORG" in base else None
    source_vorg = source["VORG"] if "VORG" in source else None

    charstrings: dict[str, object] = {}
    hmtx: dict[str, tuple[int, int]] = {}
    vmtx: dict[str, tuple[int, int]] = {}
    vorg: dict[str, int] = {}
    total = len(out_order)

    print(f"Building {total} CFF glyphs ...")
    for index, out_name in enumerate(out_order):
        if out_name in source_by_out:
            src_name = source_by_out[out_name]
            glyph_set = source_gs
            h_metrics = source_hmtx
            v_metrics = source_vmtx
            origin_table = source_vorg
        else:
            src_name = out_name
            glyph_set = base_gs
            h_metrics = base_hmtx
            v_metrics = base_vmtx
            origin_table = base_vorg

        width, lsb = h_metrics[src_name]
        pen = T2CharStringPen(width, glyph_set)
        glyph_set[src_name].draw(pen)
        charstrings[out_name] = pen.getCharString()
        hmtx[out_name] = (width, lsb)

        if include_vertical:
            # Both supplied fonts provide vertical metrics for every glyph.
            vmtx[out_name] = v_metrics[src_name]

        if origin_table is not None:
            origin = origin_table.VOriginRecords.get(
                src_name, origin_table.defaultVertOriginY
            )
            if origin != vorg_default:
                vorg[out_name] = origin

        if (index + 1) % 5000 == 0 or index + 1 == total:
            print(f"  {index + 1}/{total} glyphs")

    return charstrings, hmtx, vmtx if include_vertical else None, vorg


def cff_bbox(font: TTFont) -> list[int]:
    cff = font["CFF "].cff
    top_dict = cff[cff.fontNames[0]]
    return [int(value) for value in top_dict.FontBBox]


def union_bbox(a: list[int], b: list[int]) -> list[int]:
    return [
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(a[2], b[2]),
        max(a[3], b[3]),
    ]


def copy_layout_tables(base: TTFont, merged: TTFont) -> None:
    """Carry INPUT1's layout/BASE tables over unchanged.

    Every glyph from subsetted INPUT1 is present in the merged font, so all
    glyph references in these tables remain valid.  INPUT2's layout tables are
    intentionally not copied because their glyph set is not part of this font.
    """
    for tag in ("GSUB", "GPOS", "GDEF", "BASE"):
        if tag in base:
            merged[tag] = base[tag]


def build_merged_font(
    base: TTFont,
    source: TTFont,
    out_cmap: dict[int, str],
    out_order: list[str],
    source_by_out: dict[str, str],
    include_vertical: bool,
) -> tuple[TTFont, str]:
    units_per_em = base["head"].unitsPerEm
    bbox = union_bbox(cff_bbox(base), cff_bbox(source))

    name_table = deepcopy(base["name"])
    ps_name = name_table.getDebugName(6)
    if not ps_name:
        base_cff = base["CFF "].cff
        ps_name = base_cff.fontNames[0]
    if not ps_name:
        raise RuntimeError("Could not determine the PostScript name from INPUT1")

    base_cff = base["CFF "].cff
    base_top = base_cff[base_cff.fontNames[0]]
    font_info: dict[str, object] = {"FontBBox": bbox}
    for key in CFF_INFO_KEYS:
        value = getattr(base_top, key, None)
        if value is not None:
            font_info[key] = value
    version_match = re.search(
        r"Version\s+([0-9.]+)", name_table.getDebugName(5) or ""
    )
    font_info["version"] = version_match.group(1) if version_match else "1.000"

    include_vorg = include_vertical and ("VORG" in base or "VORG" in source)
    if "VORG" in base:
        vorg_default = base["VORG"].defaultVertOriginY
    elif "VORG" in source:
        vorg_default = source["VORG"].defaultVertOriginY
    else:
        vorg_default = 880

    charstrings, hmtx, vmtx, vorg = make_charstrings_and_metrics(
        base,
        source,
        out_order,
        source_by_out,
        include_vertical,
        vorg_default,
    )

    fb = FontBuilder(unitsPerEm=units_per_em, isTTF=False)
    fb.setupGlyphOrder(out_order)
    fb.setupHead(
        xMin=bbox[0],
        yMin=bbox[1],
        xMax=bbox[2],
        yMax=bbox[3],
        unitsPerEm=units_per_em,
        created=base["head"].created,
        modified=timestampNow(),
        flags=base["head"].flags,
        macStyle=base["head"].macStyle,
        fontRevision=base["head"].fontRevision,
        lowestRecPPEM=base["head"].lowestRecPPEM,
    )
    fb.setupCharacterMap(out_cmap, allowFallback=True)
    fb.setupCFF(
        ps_name,
        font_info,
        charstrings,
        {"defaultWidthX": 0, "nominalWidthX": 0},
    )
    fb.setupHorizontalMetrics(hmtx)

    hhea = base["hhea"]
    fb.setupHorizontalHeader(
        ascent=hhea.ascent,
        descent=hhea.descent,
        lineGap=hhea.lineGap,
        advanceWidthMax=max(width for width, _ in hmtx.values()),
        minLeftSideBearing=min(lsb for _, lsb in hmtx.values()),
        minRightSideBearing=hhea.minRightSideBearing,
        xMaxExtent=hhea.xMaxExtent,
        caretSlopeRise=hhea.caretSlopeRise,
        caretSlopeRun=hhea.caretSlopeRun,
        caretOffset=hhea.caretOffset,
    )

    if include_vertical:
        assert vmtx is not None
        vhea = base["vhea"]
        fb.setupVerticalMetrics(vmtx)
        fb.setupVerticalHeader(
            ascent=vhea.ascent,
            descent=vhea.descent,
            lineGap=vhea.lineGap,
            advanceHeightMax=max(height for height, _ in vmtx.values()),
            minTopSideBearing=min(tsb for _, tsb in vmtx.values()),
            minBottomSideBearing=vhea.minBottomSideBearing,
            yMaxExtent=vhea.yMaxExtent,
            caretSlopeRise=vhea.caretSlopeRise,
            caretSlopeRun=vhea.caretSlopeRun,
            caretOffset=vhea.caretOffset,
        )
        if include_vorg:
            fb.setupVerticalOrigins(vorg, defaultVerticalOrigin=vorg_default)

    fb.setupMaxp()

    merged = fb.font
    merged["name"] = name_table
    merged["OS/2"] = deepcopy(base["OS/2"])
    merged["post"] = deepcopy(base["post"])
    copy_layout_tables(base, merged)

    # Unicode range and codepage bits must cover the union cmap.
    merged["OS/2"].recalcUnicodeRanges(merged)
    merged["OS/2"].recalcCodePageRanges(merged)
    merged["OS/2"].recalcAvgCharWidth(merged)
    merged["OS/2"].usFirstCharIndex = min(min(out_cmap), 0xFFFF)
    merged["OS/2"].usLastCharIndex = min(max(out_cmap), 0xFFFF)

    # Use the union of both source bounding boxes rather than recalculating
    # 50k glyph bounds again during save.  This is a valid (slightly padded)
    # CFF/head bounding box and keeps head.h and CFF FontBBox consistent.
    merged.recalcBBoxes = False
    merged.recalcTimestamp = False
    head = merged["head"]
    head.xMin, head.yMin, head.xMax, head.yMax = bbox
    head.modified = timestampNow()

    if merged["name"].getDebugName(6) != ps_name:
        raise RuntimeError("CFF FontName and name ID 6 do not match")
    return merged, ps_name


def save_atomically(font: TTFont, output_path: Path, expected_cmap_size: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        font.save(temp_path)
        check = TTFont(temp_path, checkChecksums=2)
        try:
            if len(check.getBestCmap() or {}) != expected_cmap_size:
                raise RuntimeError("Saved font has an unexpected cmap size")
        finally:
            check.close()
        os.replace(temp_path, output_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    args = parse_args()
    input1_path = args.input1.expanduser().resolve()
    input2_path = args.input2.expanduser().resolve()
    output_path = args.output.expanduser().resolve()

    for label, path in (("INPUT1", input1_path), ("INPUT2", input2_path)):
        if not path.is_file():
            print(f"error: {label} not found: {path}", file=sys.stderr)
            return 1
    if output_path in (input1_path, input2_path):
        print("error: OUTPUT must differ from both input paths", file=sys.stderr)
        return 1

    started = time.perf_counter()
    base = TTFont(input1_path)
    source = TTFont(input2_path)
    try:
        for label, font in (("INPUT1", base), ("INPUT2", source)):
            if font.sfntVersion != "OTTO" or "CFF " not in font:
                print(f"error: {label} must be a CFF OpenType font", file=sys.stderr)
                return 1
            missing_tables = [tag for tag in REQUIRED_TABLES if tag not in font]
            if missing_tables:
                print(
                    f"error: {label} lacks required tables: "
                    f"{', '.join(missing_tables)}",
                    file=sys.stderr,
                )
                return 1

        upem1 = base["head"].unitsPerEm
        upem2 = source["head"].unitsPerEm
        if upem1 != upem2:
            print(
                f"error: unitsPerEm differs ({upem1} vs {upem2})",
                file=sys.stderr,
            )
            return 1

        cmap1 = get_unicode_cmap(base, "INPUT1")
        cmap2 = get_unicode_cmap(source, "INPUT2")
        keep_codepoints = {cp for cp in cmap1 if not is_cjk(cp)}
        removed_cjk = {cp for cp in cmap1 if is_cjk(cp)}

        print(f"INPUT1: {input1_path}")
        print(f"  original characters: {len(cmap1)}")
        print(f"  removed CJK characters: {len(removed_cjk)}")
        print(f"  non-CJK characters kept: {len(keep_codepoints)}")

        base_cmap = make_intermediate1(base, keep_codepoints)
        print(f"  intermediate1 glyphs: {len(base.getGlyphOrder())}")

        out_cmap, out_order, source_by_out, missing = make_merge_plan(
            base, source, base_cmap, cmap2
        )
        added_cjk = sum(1 for cp in missing if is_cjk(cp))
        print(f"INPUT2: {input2_path}")
        print(f"  characters in INPUT2: {len(cmap2)}")
        print(
            f"  added missing characters: {len(missing)} "
            f"({added_cjk} CJK, {len(missing) - added_cjk} other)"
        )

        include_vertical = all(
            tag in base and tag in source for tag in ("vhea", "vmtx")
        )
        merged, ps_name = build_merged_font(
            base,
            source,
            out_cmap,
            out_order,
            source_by_out,
            include_vertical,
        )
        try:
            save_atomically(merged, output_path, len(out_cmap))
        finally:
            merged.close()
    finally:
        base.close()
        source.close()

    elapsed = time.perf_counter() - started
    size_mib = output_path.stat().st_size / (1024 * 1024)
    print(f"OUTPUT: {output_path}")
    print(f"  characters: {len(out_cmap)}")
    print(f"  glyphs: {len(out_order)}")
    print(f"  PostScript name: {ps_name}")
    print(f"  size: {size_mib:.1f} MiB")
    print(f"Done in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
