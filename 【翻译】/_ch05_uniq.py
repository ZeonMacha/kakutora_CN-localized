# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter

ROOT = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本")
SRC = ROOT / "stories"
texts = Counter()
for p in sorted(SRC.glob("dd_ch05_*.json")):
    data = json.loads(p.read_text(encoding="utf-8"))
    for e in data["entry"]:
        texts[e["text"]] += 1
print("unique", len(texts), "total", sum(texts.values()))
print("dup_entries", sum(v for v in texts.values() if v > 1))
# longest
longs = sorted(texts, key=len, reverse=True)[:5]
for t in longs:
    print("LEN", len(t), "count", texts[t])
