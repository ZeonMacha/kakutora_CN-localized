# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本\【翻译】\文风.md")
text = p.read_text(encoding="utf-8")
idx = text.find("ぜよ")
print("idx", idx)
chunk = text[idx:idx+80]
print(chunk)
print([hex(ord(c)) for c in chunk])
