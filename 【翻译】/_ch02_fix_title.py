# -*- coding: utf-8 -*-
import json
from pathlib import Path
p = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本\【翻译】\stories\dd_ch02_06_101.json")
data = json.loads(p.read_text(encoding="utf-8"))
old = data["info"]["sub_title_zh"]
data["info"]["sub_title_zh"] = old.replace("出陣", "出击")
text = json.dumps(data, ensure_ascii=False, indent=4) + "\n"
p.write_text(text, encoding="utf-8")
print(old, "->", data["info"]["sub_title_zh"])
