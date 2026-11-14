# -*- coding: utf-8 -*-
import json
from pathlib import Path
p = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本\【翻译】\stories\dd_ch01_14_020.json")
data = json.loads(p.read_text(encoding="utf-8"))
for e in data["entry"]:
    zh = e.get("zh", "")
    for c in zh:
        if ord(c) in (0x5575, 0x557C, 0x55E1):
            print(hex(ord(c)), e["location"], zh.replace("\n", "/"))
            break
