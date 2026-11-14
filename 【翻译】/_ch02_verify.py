# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path

ROOT = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本")
SRC = ROOT / "stories"
OUT = ROOT / "【翻译】" / "stories"
KANA = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff]")
BAD = "\u7efd\u7ece\u7edb\u55e1\u54fd\u60a8"
files = sorted(p.name for p in SRC.glob("dd_ch02_*.json"))
done = []
total = 0
for name in files:
    outp = OUT / name
    if not outp.exists():
        print("NEXT", name)
        break
    src = json.loads((SRC / name).read_text(encoding="utf-8"))
    out = json.loads(outp.read_text(encoding="utf-8"))
    assert len(src["entry"]) == len(out["entry"])
    for a, b in zip(src["entry"], out["entry"]):
        assert a["text"] == b["text"] and a["narrator"] == b["narrator"] and a["location"] == b["location"]
        assert b["zh"] and a["text"].count("\n") == b["zh"].count("\n")
        assert not any(c in b["zh"] for c in BAD)
        assert "卵月" not in b["zh"] and "蛍" not in b["zh"]
        for c in b["zh"]:
            if KANA.match(c):
                assert c in a["text"], (name, c, b["zh"])
        if a["narrator"].strip() == "アーヤ":
            assert [ord(c) for c in b["narrator_zh"]] == [0x7EEB, 0x6C34]
        if a["narrator"] == "":
            assert b["narrator_zh"] == ""
    n = len(out["entry"])
    total += n
    done.append((name, n, out["info"].get("title_zh"), out["info"].get("sub_title_zh")))
print("FILES", len(done), "ENTRIES", total)
for row in done:
    print("\t".join(str(x) for x in row))
