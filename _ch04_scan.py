# -*- coding: utf-8 -*-
import json, os, glob, collections

root = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(root, "stories")
out_dir = os.path.join(root, "【翻译】", "stories")
files = sorted(glob.glob(os.path.join(src_dir, "dd_ch04_*.json")))

tm = {}
for p in glob.glob(os.path.join(out_dir, "*.json")):
    if os.path.basename(p).startswith("dd_ch04_"):
        continue
    try:
        data = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    for e in data.get("entry") or []:
        t = e.get("text")
        z = e.get("zh")
        if t and z and t not in tm:
            tm[t] = z

rows = []
narr = collections.Counter()
total = 0
hit = 0
miss_chars = 0
for p in files:
    data = json.load(open(p, encoding="utf-8"))
    n = len(data["entry"])
    h = 0
    mc = 0
    for e in data["entry"]:
        narr[e.get("narrator") or ""] += 1
        t = e.get("text") or ""
        if t in tm:
            h += 1
        else:
            mc += len(t)
    total += n
    hit += h
    miss_chars += mc
    rows.append((os.path.basename(p), n, h, n - h, data["info"].get("story_id"), data["info"].get("title"), data["info"].get("sub_title")))

print("FILES", len(files))
print("ENTRIES", total)
print("TM_HIT", hit)
print("TM_MISS", total - hit)
print("MISS_CHARS", miss_chars)
print("---NARR---")
for k, v in narr.most_common():
    print(f"{v}\t{k}")
print("---FILES---")
for r in rows:
    print("\t".join(str(x) for x in r))
