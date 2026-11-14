# -*- coding: utf-8 -*-
import json
from pathlib import Path

ROOT = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本")
SRC = ROOT / "stories"
OUT = ROOT / "【翻译】" / "stories"
TITLES = json.loads((ROOT / "【翻译】" / "专名" / "主线标题.json").read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in TITLES["rows"]}

files = sorted(SRC.glob("dd_ch05_*.json"))
narrs = {}
total = 0
print("FILES", len(files))
for p in files:
    data = json.loads(p.read_text(encoding="utf-8"))
    n = len(data["entry"])
    total += n
    info = data["info"]
    row = by_id.get(info["story_id"])
    sub = info["sub_title"]
    base = sub.replace("＜前編＞", "").replace("＜後編＞", "")
    ok = ""
    if row is None:
        ok = "NO_ID"
    elif row["副标题"] != base and row["副标题"] != sub:
        ok = "SUB_MISMATCH table=" + row["副标题"]
    else:
        ok = row["中文副标题"]
    done = (OUT / p.name).exists()
    print(f"{p.name}\t{n}\t{info['story_id']}\t{info['title']}\t{sub}\t{ok}\tdone={done}")
    for e in data["entry"]:
        narrs[e["narrator"]] = narrs.get(e["narrator"], 0) + 1
print("TOTAL", total)
print("---NARRATORS---")
for k, v in sorted(narrs.items(), key=lambda kv: -kv[1]):
    print(f"{v}\t{k}")
