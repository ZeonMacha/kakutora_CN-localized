# -*- coding: utf-8 -*-
"""Lookup glossary hits for ch05 narrators and odd title strings. Do not edit glossary."""
import json
from pathlib import Path

ROOT = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本")
gloss = json.loads((ROOT / "【翻译】" / "专名" / "对照.json").read_text(encoding="utf-8"))
keys = [
    "ぴょんこ", "月神楽", "アースタシア", "拘束されし者", "ソイルトン", "珠緒",
    "スピネル", "モーフィス", "原初の千羽鶴", "赤髪千羽鶴", "昇華", "文雄",
    "音羽", "北斎", "SAKI", "一之宮", "KAGURA", "アーケロン", "珠緒先生",
    "プレイヤー", "アナウンス", "オペレーター", "パイロット", "全権大使",
    "月神楽", "卯月神楽", "卯月神楽", "繭", "真幌", "眞幌",
]
for item in gloss:
    jp = item["jp"]
    if any(k in jp for k in keys):
        print(jp, "=>", item["zh"])
