# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

SRC = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本\stories")
name = sys.argv[1]
data = json.loads((SRC / name).read_text(encoding="utf-8"))
info = data["info"]
print("TITLE", info.get("title"))
print("SUB", info.get("sub_title"))
print("ID", info.get("story_id"))
print("N", len(data["entry"]))
for i, e in enumerate(data["entry"]):
    text = e["text"].replace("\n", "\\n")
    print(f"{i}\t{e['location']}\t{e['narrator']}\t{text}")
