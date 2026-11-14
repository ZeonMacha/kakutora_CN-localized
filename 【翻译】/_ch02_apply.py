# -*- coding: utf-8 -*-
"""Write one dd_ch02 translation. Skip a valid existing file. Do not edit glossary."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本")
SRC = ROOT / "stories"
OUT = ROOT / "【翻译】" / "stories"
GLOSS_PATH = ROOT / "【翻译】" / "专名" / "对照.json"
STYLE = ROOT / "【翻译】" / "文风.md"
TITLES = ROOT / "【翻译】" / "专名" / "主线标题.json"
SAMPLE = OUT / "dd_ch01_15_101.json"

gloss = {x["jp"]: x["zh"] for x in json.loads(GLOSS_PATH.read_text(encoding="utf-8"))}
AYA = gloss["アーヤ"]
FULL = gloss["國政綾水"]
assert [ord(c) for c in AYA] == [0x7EEB, 0x6C34]
assert [ord(c) for c in FULL[:2]] == [0x56FD, 0x653F]
assert FULL[2:] == AYA

style = STYLE.read_text(encoding="utf-8")
mark = style.find("ぜよ")
BO = style[style.find("用「", mark) + 2]
assert ord(BO) == 0x5575
assert ord(BO) != 0x55E1

title_rows = {r["id"]: r for r in json.loads(TITLES.read_text(encoding="utf-8"))["rows"]}

sample_battle = {}
if SAMPLE.exists():
    for e in json.loads(SAMPLE.read_text(encoding="utf-8"))["entry"]:
        if str(e.get("narrator", "")).startswith("BattleInit"):
            sample_battle[e["text"]] = e["zh"]

KANA = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff]")
FORBIDDEN = "\u7efd\u7ece\u7edb\u55e1\u54fd\u60a8"  # 绽绎绛噻哽您

OVERLAY = {
    "": "",
    "繭": "茧",
    "（選択肢）": "（选项）",
    "プレイヤー": "玩家",
    "車内アナウンス": "车内广播",
    "ウェイトレス": "女服务员",
    "通常攻撃隊Ａ": "通常攻击队A",
    "職員Ａ": "职员A",
    "高校生アーヤ": "高中生" + AYA,
    "現実世界のアーヤ": "现实世界的" + AYA,
    "アーヤの新司書": AYA + "的新司书",
    "國政綾水": FULL,
    "アーヤ": AYA,
}


def narrator_zh(name: str) -> str:
    if name in ("INFO", "NOTICE", "YES_NO") or name.startswith("Dialog") or name.startswith("BattleInit"):
        return name
    key = name.strip()
    if key in OVERLAY:
        return OVERLAY[key]
    if key in gloss:
        return gloss[key]
    if key.startswith("透明"):
        return "透明" + narrator_zh(key[2:])
    if key.startswith("高校生"):
        return "高中生" + narrator_zh(key[3:])
    if key.startswith("現実世界の"):
        return "现实世界的" + narrator_zh(key[len("現実世界の"):])
    raise KeyError(name)


def title_pair(info):
    sid = str(info["story_id"])
    row = title_rows.get(sid)
    if row is None:
        stem = info["sub_title"]
        for suf in ("＜前編＞", "＜後編＞"):
            if stem.endswith(suf):
                stem = stem[: -len(suf)]
        hits = [r for r in title_rows.values() if r.get("副标题") == stem]
        if len(hits) != 1:
            raise SystemExit(f"no title row {sid} {info['sub_title']} hits={len(hits)}")
        row = hits[0]
    title = info["title"]
    col2, col3 = row.get("col2") or "", row.get("col3") or ""
    if col2 and col2 in title:
        tz = title.replace(col2, col3)
    else:
        tz = title.replace("メインストーリー", "主线剧情").replace("プレミアムストーリー", "额外剧情").replace("ストーリー", "剧情")
    sub = info["sub_title"]
    base = row.get("中文副标题") or ""
    suffix = ""
    if sub.endswith("＜前編＞"):
        suffix = "＜前篇＞"
        if base.endswith("＜前篇＞"):
            suffix = ""
    elif sub.endswith("＜後編＞"):
        suffix = "＜后篇＞"
        if base.endswith("＜后篇＞"):
            suffix = ""
    sz = base + suffix
    for src_bit, dst_bit in (("出陣", "出击"), ("爆殺", "爆杀")):
        tz = tz.replace(src_bit, dst_bit)
        sz = sz.replace(src_bit, dst_bit)
    if ("綾水" in sub or "國政綾水" in sub) and AYA not in sz:
        raise SystemExit(f"title missing AYA {sid} {sz}")
    return tz, sz


def expand(s: str) -> str:
    return s.replace("{AYA}", AYA).replace("{FULL}", FULL).replace("{BO}", BO)


def valid_existing(src, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        out = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if len(out.get("entry", [])) != len(src["entry"]):
        return False
    for a, b in zip(src["entry"], out["entry"]):
        if not b.get("zh"):
            return False
    return True


def apply(filename: str, zhs: list) -> None:
    src = json.loads((SRC / filename).read_text(encoding="utf-8"))
    outp = OUT / filename
    if valid_existing(src, outp):
        print("SKIP", filename, len(src["entry"]))
        return
    if len(zhs) != len(src["entry"]):
        raise SystemExit(f"{filename} count {len(zhs)} != {len(src['entry'])}")
    data = json.loads((SRC / filename).read_text(encoding="utf-8"))
    tz, sz = title_pair(data["info"])
    errs = []
    for i, (e, raw) in enumerate(zip(data["entry"], zhs)):
        if e["narrator"].startswith("BattleInit") and e["text"] in sample_battle:
            zh = sample_battle[e["text"]]
        else:
            zh = expand(raw)
        if e["text"].strip(" \u3000") == "" and e["text"]:
            zh = "……"
        if not zh or not zh.strip():
            raise SystemExit(f"empty {filename} {i} {e['location']}")
        if e["text"].count("\n") != zh.count("\n"):
            errs.append(f"newlines {filename} {i} {e['location']}\nSRC:{e['text']!r}\nZH:{zh!r}")
            e["zh"] = zh
            e["narrator_zh"] = ""
            continue
        for tok in ("$me$", "$handle$", "$chrname$"):
            if e["text"].count(tok) != zh.count(tok):
                raise SystemExit(f"token {tok} {filename} {i}")
        bad = [c for c in FORBIDDEN if c in zh]
        if bad:
            raise SystemExit(f"forbidden {filename} {i} {[hex(ord(c)) for c in bad]} {zh!r}")
        if "卵月" in zh or "蛍" in zh:
            raise SystemExit(f"bad name {filename} {i} {zh!r}")
        for c in zh:
            if KANA.match(c) and c not in e["text"]:
                raise SystemExit(f"new kana {filename} {i} {c} {zh!r}")
        nz = narrator_zh(e["narrator"])
        if e["narrator"].strip() == "アーヤ":
            assert [ord(c) for c in nz] == [0x7EEB, 0x6C34]
        if e["narrator"].strip() == "" and nz != "":
            raise SystemExit(f"empty narrator {filename} {i}")
        e["zh"] = zh
        e["narrator_zh"] = nz
    if errs:
        raise SystemExit("\n".join(errs))
    data["info"]["title_zh"] = tz
    data["info"]["sub_title_zh"] = sz
    text = json.dumps(data, ensure_ascii=False, indent=4) + "\n"
    # validate roundtrip before write
    back = json.loads(text)
    if len(back["entry"]) != len(src["entry"]):
        raise SystemExit("count")
    for a, b in zip(src["entry"], back["entry"]):
        if a["text"] != b["text"] or a["narrator"] != b["narrator"] or a["location"] != b["location"]:
            raise SystemExit("source field changed")
        if not b["zh"]:
            raise SystemExit("empty zh after dump")
        if a["text"].count("\n") != b["zh"].count("\n"):
            raise SystemExit("newline after dump")
    outp.write_text(text, encoding="utf-8")
    print("WROTE", filename, len(src["entry"]), tz, sz)


def main():
    mod = __import__(sys.argv[1])
    apply(mod.FILENAME, mod.ZHS)


if __name__ == "__main__":
    main()
