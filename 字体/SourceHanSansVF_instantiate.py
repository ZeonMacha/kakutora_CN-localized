#!/usr/bin/env python3
"""Create a static, single-weight OTF from the Source Han Sans SC variable font.

This fully pins the ``wght`` variation axis at the requested value and writes a
static OTF to the requested output path.  Because the source is a CFF2 variable
font, the fully pinned instance is also downgraded to CFF so it can be used by
software that does not understand variable fonts or CFF2.

fontTools' instancer warns that it does not update VORG from VVAR when pinning
the weight axis, so this script materializes those vertical-origin deltas too.

Usage:
    python instantiate_wght450.py SOURCE WGHT OUTPUT

Example:
    python instantiate_wght450.py SourceHanSansSC-VF.otf 450 \
        SourceHanSansSC-450.otf

Requires a fontTools version with CFF2-to-CFF downgrade support (tested with
fontTools 4.60.2).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import time
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import AxisLimits, instantiateVariableFont
from fontTools.varLib.varStore import VarStoreInstancer

# Windows Unicode (BMP) name records used by this font.
LANG_EN_US = 0x0409
LANG_ZH_CN = 0x0804
PLATFORM_WINDOWS = 3
PLATFORM_WINDOWS_UNICODE_BMP = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fully instantiate a variable font at a single wght value and "
            "produce a static CFF OTF."
        )
    )
    parser.add_argument(
        "input",
        metavar="SOURCE",
        type=Path,
        help="variable font input, e.g. SourceHanSansSC-VF.otf",
    )
    parser.add_argument(
        "weight",
        metavar="WGHT",
        type=int,
        help="wght value to pin, e.g. 450",
    )
    parser.add_argument(
        "output",
        metavar="OUTPUT",
        type=Path,
        help="static OTF output, e.g. SourceHanSansSC-450.otf",
    )
    return parser.parse_args()


def localized_name(font: TTFont, name_id: int, lang_id: int) -> str | None:
    for record in font["name"].names:
        if (
            record.nameID == name_id
            and record.platformID == PLATFORM_WINDOWS
            and record.platEncID == PLATFORM_WINDOWS_UNICODE_BMP
            and record.langID == lang_id
        ):
            return record.toUnicode()
    return None


def static_family_name(source_family: str | None, weight: int) -> str:
    family = re.sub(r"\s*VF\s*$", "", (source_family or "").strip())
    if not family:
        family = "Source Han Sans SC"
    suffix = f" {weight}"
    if not family.endswith(suffix):
        family += suffix
    return family


def update_names(
    font: TTFont, input_path: Path, weight: int
) -> tuple[str, str]:
    """Give the instance unique family/PostScript names and set RIBBI style."""
    name_table = font["name"]
    family_en = static_family_name(localized_name(font, 1, LANG_EN_US), weight)
    source_family_zh = localized_name(font, 1, LANG_ZH_CN)
    family_zh = (
        static_family_name(source_family_zh, weight) if source_family_zh else None
    )

    ps_base = re.sub(r"[-_]?VF$", "", input_path.stem, flags=re.IGNORECASE)
    ps_base = re.sub(r"[^A-Za-z0-9.-]", "", ps_base) or "SourceHanSansSC"
    postscript_name = f"{ps_base}-{weight}"

    old_postscript = name_table.getDebugName(6) or ""
    old_unique_id = name_table.getDebugName(3) or ""
    if old_postscript and old_postscript in old_unique_id:
        unique_id = old_unique_id.replace(old_postscript, postscript_name)
    else:
        version_match = re.search(
            r"Version\s+([0-9.]+)", name_table.getDebugName(5) or ""
        )
        version = version_match.group(1) if version_match else "1.000"
        unique_id = f"{version};ADBO;{postscript_name};ADOBE"

    def set_windows_name(name_id: int, english: str, chinese: str | None = None) -> None:
        name_table.setName(
            english,
            name_id,
            PLATFORM_WINDOWS,
            PLATFORM_WINDOWS_UNICODE_BMP,
            LANG_EN_US,
        )
        if chinese is not None:
            name_table.setName(
                chinese,
                name_id,
                PLATFORM_WINDOWS,
                PLATFORM_WINDOWS_UNICODE_BMP,
                LANG_ZH_CN,
            )

    set_windows_name(1, family_en, family_zh)  # Font Family
    set_windows_name(2, "Regular", "Regular")  # Font Subfamily
    set_windows_name(3, unique_id)  # Unique Font Identifier
    set_windows_name(4, family_en, family_zh)  # Full Font Name
    set_windows_name(6, postscript_name)  # PostScript Name
    set_windows_name(17, "Regular", "Regular")  # Typographic Subfamily

    # Keep typographic family in sync if the source has one.
    typographic_family = localized_name(font, 16, LANG_EN_US)
    if typographic_family is not None:
        set_windows_name(
            16,
            family_en,
            family_zh if localized_name(font, 16, LANG_ZH_CN) else None,
        )

    # The CFF2->CFF downgrade leaves the placeholder internal name
    # "CFF2Font" and does not emit CIDCount.  Both are required for a clean
    # CID-keyed CFF font, so align them with the instance before saving.
    if "CFF " in font:
        cff = font["CFF "].cff
        cff.fontNames[0] = postscript_name
        top_dict = cff.topDictIndex[0]
        top_dict.CIDCount = len(font.getGlyphOrder())
        top_dict.FamilyName = family_en
        top_dict.FullName = family_en
        top_dict.Weight = "Regular"

    return family_en, postscript_name


def apply_vorg_deltas(font: TTFont, weight: int) -> int:
    """Apply VVAR vertical-origin deltas to VORG before it is frozen.

    fontTools 4.60 updates vmtx from VVAR but warns that VORG is not updated.
    The deltas are harmless for horizontal layout but matter for vertical CJK
    typesetting, so compute them at the pinned location and bake them in.
    """
    if "VVAR" not in font or "VORG" not in font:
        return 0

    vvar = font["VVAR"].table
    if vvar.VOrgMap is None:
        return 0

    normalized_limits = (
        AxisLimits({"wght": weight})
        .limitAxesAndPopulateDefaults(font)
        .normalize(font)
    )
    instancer = VarStoreInstancer(
        vvar.VarStore,
        font["fvar"].axes,
        normalized_limits.pinnedLocation(),
    )

    vorg = font["VORG"]
    updated = 0
    for glyph_name, var_index in vvar.VOrgMap.mapping.items():
        delta = round(instancer[var_index])
        if delta:
            base = vorg.VOriginRecords.get(glyph_name, vorg.defaultVertOriginY)
            vorg.VOriginRecords[glyph_name] = base + delta
            updated += 1
    return updated


def set_static_style_bits(font: TTFont, weight: int) -> None:
    """Mark the generated face as a regular, non-italic static weight."""
    os2 = font["OS/2"]
    os2.usWeightClass = weight

    # fsSelection bits: 0 = italic, 5 = bold, 6 = regular.
    os2.fsSelection = (os2.fsSelection & ~0x21) | 0x40

    # head.macStyle bits: 0 = bold, 1 = italic.
    font["head"].macStyle &= ~0x03


def assert_static(font: TTFont, weight: int) -> None:
    """Fail fast if any variation data survived the full instantiation."""
    if "fvar" in font:
        raise RuntimeError("Output still contains an 'fvar' table")
    if "CFF " not in font:
        raise RuntimeError("CFF2 was not downgraded to CFF")
    for tag in ("CFF2", "gvar", "cvar", "avar", "HVAR", "VVAR", "MVAR"):
        if tag in font:
            raise RuntimeError(f"Output still contains variation table '{tag}'")
    if font["OS/2"].usWeightClass != weight:
        raise RuntimeError(
            f"OS/2.usWeightClass is {font['OS/2'].usWeightClass}, expected {weight}"
        )

    cff = font["CFF "].cff
    postscript_name = font["name"].getDebugName(6)
    if not cff.fontNames or cff.fontNames[0] != postscript_name:
        raise RuntimeError(
            f"CFF FontName {cff.fontNames!r} does not match name ID 6 "
            f"{postscript_name!r}"
        )
    if cff.topDictIndex[0].CIDCount != len(font.getGlyphOrder()):
        raise RuntimeError("CFF CIDCount does not match the glyph count")


def save_atomically(font: TTFont, output_path: Path) -> None:
    """Write to a temporary file, then replace the destination atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        font.save(temp_path)
        os.replace(temp_path, output_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    weight = args.weight

    if not input_path.is_file():
        print(f"error: input font not found: {input_path}", file=sys.stderr)
        return 1
    if output_path == input_path:
        print("error: output path must differ from input path", file=sys.stderr)
        return 1
    if not 1 <= weight <= 1000:
        print("error: WGHT must be between 1 and 1000", file=sys.stderr)
        return 1

    started = time.perf_counter()
    font = TTFont(input_path)
    try:
        fvar = font.get("fvar")
        if fvar is None:
            print(f"error: input is not a variable font: {input_path}", file=sys.stderr)
            return 1

        axes = {axis.axisTag: axis for axis in fvar.axes}
        if "wght" not in axes:
            print("error: input font has no 'wght' axis", file=sys.stderr)
            return 1
        wght = axes["wght"]
        if not wght.minValue <= weight <= wght.maxValue:
            print(
                "error: wght="
                f"{weight} is outside the font's axis range "
                f"[{wght.minValue:g}, {wght.maxValue:g}]",
                file=sys.stderr,
            )
            return 1

        source_glyph_count = len(font.getGlyphOrder())
        print(f"Input:  {input_path}")
        print(f"Pinning wght={weight} ...")

        vorg_updates = apply_vorg_deltas(font, weight)
        if vorg_updates:
            print(f"Applying VVAR deltas to {vorg_updates} VORG records ...")

        # static=True also pins any other axes to their defaults, guaranteeing a
        # fully static font.  downgradeCFF2 turns the CFF2 outlines into CFF.
        instantiateVariableFont(
            font,
            {"wght": weight},
            inplace=True,
            updateFontNames=False,
            downgradeCFF2=True,
            static=True,
        )

        family_name, postscript_name = update_names(font, input_path, weight)
        set_static_style_bits(font, weight)
        assert_static(font, weight)

        if len(font.getGlyphOrder()) != source_glyph_count:
            raise RuntimeError("Glyph count changed during instantiation")

        save_atomically(font, output_path)
    finally:
        font.close()

    elapsed = time.perf_counter() - started
    size_mib = output_path.stat().st_size / (1024 * 1024)
    print(f"Output: {output_path} ({size_mib:.1f} MiB)")
    print(f"Static face: {family_name} / Regular")
    print(f"PostScript:  {postscript_name}")
    print(f"Done in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
