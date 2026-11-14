# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter

SRC = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本\stories")
files = sorted(SRC.glob("dd_ch02_*.json"))
total = 0
narr = Counter()
for p in files:
    data = json.loads(p.read_text(encoding="utf-8"))
    n = len(data["entry"])
    total += n
    info = data["info"]
    for e in data["entry"]:
        narr[e.get("narrator", "")] += 1
    print(f"{p.name}\t{n}\t{info.get('story_id')}\t{info.get('title')}\t{info.get('sub_title')}")
print("TOTAL", total, "FILES", len(files))
print("---NARRATORS---")
for k, v in narr.most_common():
    print(f"{v}\t{k}")
