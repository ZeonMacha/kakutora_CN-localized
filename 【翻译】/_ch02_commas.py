# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本\【翻译】\_z_dd_ch02_08_020.py")
lines = p.read_text(encoding="utf-8").splitlines()
for i, line in enumerate(lines, 1):
    s = line.rstrip()
    if s.endswith('"') and not s.endswith(',"') and i < len(lines):
        nxt = lines[i].lstrip()
        if nxt.startswith('"'):
            print(i, s[-40:])
