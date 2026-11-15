# -*- coding: utf-8 -*-
"""Merge story translations. Skip outputs that already exist. Stop before the deadline."""
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本"
SRC = os.path.join(BASE, "stories")
DST = os.path.join(BASE, "【翻译】", "stories")
GLOSS_PATH = os.path.join(BASE, "【翻译】", "专名", "对照.json")
TR_DIR = os.path.join(BASE, "_tr_data")
DEADLINE = datetime(2026, 11, 11, 14, 50, tzinfo=ZoneInfo("Asia/Shanghai"))
FORBIDDEN = {0x567B, 0x54FD, 0x5566, 0x7EFD}

gloss = {item["jp"]: item["zh"] for item in json.load(open(GLOSS_PATH, encoding="utf-8"))}
NARRATOR_EXTRA = {"（選択肢）": "（选项）"}


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai"))


def parse_tr(path):
    raw = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    head, body = raw.split("\n<<<\n", 1)
    lines = head.split("\n")
    title = sub = None
    for line in lines:
        if line.startswith("TITLE\t"):
            title = line.split("\t", 1)[1]
        elif line.startswith("SUB\t"):
            sub = line.split("\t", 1)[1]
    if title is None or sub is None:
        raise SystemExit(f"missing title header: {path}")
    parts = body.split("\n<<<\n")
    if parts and parts[-1] == "":
        parts.pop()
    return title, sub, parts


def narrator_zh(nar):
    if nar == "":
        return ""
    if nar in gloss:
        return gloss[nar]
    if nar in NARRATOR_EXTRA:
        return NARRATOR_EXTRA[nar]
    if "/" in nar or nar.isascii():
        return nar
    raise SystemExit(f"unknown narrator: {nar}")


def check_pair(fn, src, zh, where):
    if zh == "":
        raise SystemExit(f"empty zh {fn} {where}")
    for ch in zh:
        if ord(ch) in FORBIDDEN:
            raise SystemExit(f"forbidden U+{ord(ch):04X} {fn} {where}")
    for tok in ("$me$", "$handle$"):
        if src.count(tok) != zh.count(tok):
            raise SystemExit(f"token {tok} {fn} {where} src={src.count(tok)} zh={zh.count(tok)}")
    for tag in ("<color", "</color>", "<size", "</size>", "<b>", "</b>"):
        if src.count(tag) != zh.count(tag):
            raise SystemExit(f"tag {tag} {fn} {where}")
    if src.count("[") != zh.count("[") or src.count("]") != zh.count("]"):
        raise SystemExit(f"brackets {fn} {where}")


def apply_one(fn):
    out_path = os.path.join(DST, fn)
    if os.path.exists(out_path):
        print("SKIP", fn)
        return "skip"
    if now() >= DEADLINE:
        print("DEADLINE", fn)
        return "deadline"
    tr_path = os.path.join(TR_DIR, fn.replace(".json", ".txt"))
    if not os.path.exists(tr_path):
        print("NO_TR", fn)
        return "missing"
    title_zh, sub_title_zh, parts = parse_tr(tr_path)
    data = json.load(open(os.path.join(SRC, fn), encoding="utf-8"))
    entries = data["entry"]
    if len(parts) != len(entries):
        raise SystemExit(f"count {fn}: tr={len(parts)} src={len(entries)}")
    check_pair(fn, data["info"].get("title", ""), title_zh, "title")
    check_pair(fn, data["info"].get("sub_title", ""), sub_title_zh, "sub")
    data["info"]["title_zh"] = title_zh
    data["info"]["sub_title_zh"] = sub_title_zh
    for e, zh in zip(entries, parts):
        check_pair(fn, e.get("text", ""), zh, e.get("location"))
        e["zh"] = zh
        e["narrator_zh"] = narrator_zh(e.get("narrator", ""))
        sn = e["text"].count("\n")
        zn = zh.count("\n")
        if sn != zn:
            print(f"  lines {fn} {e.get('location')}: src={sn} zh={zn}")
    os.makedirs(DST, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")
    print("WROTE", fn, len(entries), now().strftime("%H:%M:%S"))
    return "wrote"


def main(files):
    print("now", now().isoformat())
    for fn in files:
        status = apply_one(fn)
        if status == "deadline":
            break


if __name__ == "__main__":
    main(sys.argv[1:])
