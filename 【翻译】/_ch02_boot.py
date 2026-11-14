# -*- coding: utf-8 -*-
"""Load glossary, particle, titles. Print checks. Do not edit glossary."""
import json
import re
from pathlib import Path

ROOT = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本")
GLOSS_PATH = ROOT / "【翻译】" / "专名" / "对照.json"
STYLE = ROOT / "【翻译】" / "文风.md"
TITLES = ROOT / "【翻译】" / "专名" / "主线标题.json"
ANIME = ROOT / "【翻译】" / "专名" / "主线动画标题.json"

gloss_list = json.loads(GLOSS_PATH.read_text(encoding="utf-8"))
gloss = {x["jp"]: x["zh"] for x in gloss_list}

AYA = gloss["アーヤ"]
FULL = gloss["國政綾水"]
assert [ord(c) for c in AYA] == [0x7EEB, 0x6C34]
assert [ord(c) for c in FULL[:2]] == [0x56FD, 0x653F]
assert FULL[2:] == AYA

style = STYLE.read_text(encoding="utf-8")
# particle sits in 「…」 right after 用
m = re.search(r"用「(.)」", style)
assert m, "particle not found"
BO = m.group(1)
assert ord(BO) != 0x55E1  # 噻
assert BO != "啥"
print("AYA", [hex(ord(c)) for c in AYA])
print("FULL", [hex(ord(c)) for c in FULL])
print("BO", hex(ord(BO)), BO)
print("gloss", len(gloss))
