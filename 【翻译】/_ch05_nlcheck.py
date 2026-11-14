# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

ROOT = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本")
pack = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
src = json.loads((ROOT / "stories" / pack["file"]).read_text(encoding="utf-8"))
zhs = pack["zhs"]
print("count", len(zhs), len(src["entry"]))
for i, (e, zh) in enumerate(zip(src["entry"], zhs)):
    a = e["text"].count("\n")
    b = zh.count("\n")
    if a != b:
        print("---", i, e["location"], "src", a, "zh", b)
        print("SRC", e["text"])
        print("ZH", zh)
