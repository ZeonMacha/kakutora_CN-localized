# -*- coding: utf-8 -*-
"""Write one dd_ch05 translation. Does not edit glossary or sources."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本")
SRC = ROOT / "stories"
OUT = ROOT / "【翻译】" / "stories"
GLOSS_PATH = ROOT / "【翻译】" / "专名" / "对照.json"
STYLE = ROOT / "【翻译】" / "文风.md"

gloss_list = json.loads(GLOSS_PATH.read_text(encoding="utf-8"))
gloss = {x["jp"]: x["zh"] for x in gloss_list}
AYA = gloss["アーヤ"]
FULL = gloss["國政綾水"]
assert [ord(c) for c in AYA] == [0x7EEB, 0x6C34]
assert FULL.endswith(AYA)

style = STYLE.read_text(encoding="utf-8")
m = re.search(r"用「(.)」。不用", style)
assert m, "particle missing"
BO = m.group(1)
assert ord(BO) == 0x5575, hex(ord(BO))

# kana letters; keep the title middle dot ・ (U+30FB)
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff\uff66-\uff9f]")
FORBIDDEN = "\u7efd\u7ece\u7edb\u567b\u54fd\u60a8"  # 绽绎绛噻哽您
# compatibility 神 -> 神 for glossary lookup only
NORM = str.maketrans({"\ufa19": "\u795e", "\u66f8": "\u4e66"})

PASSTHRU_PREFIX = ("Dialog", "dialog_", "BattleInit", "Event/")
PASSTHRU_EXACT = {"INFO", "NOTICE"}

EXTRA = {
    "プレイヤー": "玩家",
    "オペレーター": "操作员",
    "パイロット": "飞行员",
    "システム": "系统",
    "？？？": "？？？",
    "北斎": "北斋",
    "SAKI@USS": "SAKI@USS",
    "昇華Ｎ／Ａ": "升华N/A",
    "神楽の新司書": gloss.get("神楽の新司书", "神乐的新司书"),
    "繭": "茧",
    "真幌": "真幌",
}


def narr_zh(name: str) -> str:
    if name == "":
        return ""
    if name in PASSTHRU_EXACT or name.startswith(PASSTHRU_PREFIX):
        return name
    key = name.strip()
    if key in gloss:
        return gloss[key]
    norm = key.translate(NORM)
    if norm in gloss:
        return gloss[norm]
    if key in EXTRA:
        return EXTRA[key]
    if norm in EXTRA:
        return EXTRA[norm]
    if key.startswith("透明"):
        return "透明" + narr_zh(key[2:])
    if key.startswith("昇華"):
        return "升华" + narr_zh(key[2:])
    raise KeyError(name)


def subst(zh: str) -> str:
    return zh.replace("{FULL}", FULL).replace("{AYA}", AYA).replace("{BO}", BO)


def apply(filename: str, title_zh: str, sub_title_zh: str, zhs: list) -> None:
    outp = OUT / filename
    if outp.exists():
        print("SKIP", filename)
        return
    data = json.loads((SRC / filename).read_text(encoding="utf-8"))
    entries = data["entry"]
    if len(zhs) != len(entries):
        raise SystemExit(f"{filename} count {len(zhs)} != {len(entries)}")
    for i, (e, zh) in enumerate(zip(entries, zhs)):
        zh = subst(zh)
        if not isinstance(zh, str) or zh.strip() == "":
            raise SystemExit(f"empty {filename} #{i} {e['location']}")
        for tok in set(re.findall(r"\$[A-Za-z0-9_]+\$", e["text"])):
            if e["text"].count(tok) != zh.count(tok):
                raise SystemExit(f"token {tok} {filename} #{i}")
        if e["text"].count("\n") != zh.count("\n"):
            raise SystemExit(
                f"newlines {filename} #{i} {e['location']} src={e['text'].count(chr(10))} zh={zh.count(chr(10))}\nSRC:{e['text']!r}\nZH:{zh!r}"
            )
        bad = [c for c in FORBIDDEN if c in zh]
        if bad:
            raise SystemExit(f"forbidden {bad} {filename} #{i}: {zh}")
        kana = KANA.findall(zh)
        if kana:
            raise SystemExit(f"kana {kana} {filename} #{i} {e['location']}: {zh}")
        for tok in ("$me$", "$handle$", "$chrname$"):
            if e["text"].count(tok) != zh.count(tok):
                raise SystemExit(f"token {tok} {filename} #{i}")
        for word in ("哥", "姐", "老子", "人家"):
            if word in zh:
                raise SystemExit(f"{word} {filename} #{i}: {zh}")
        if AYA in zh:
            # must be the glossary string, already substituted
            pass
        e["zh"] = zh
        e["narrator_zh"] = narr_zh(e["narrator"])
        if e["narrator"] == "" and e["narrator_zh"] != "":
            raise SystemExit("narrator_zh not empty")
    data["info"]["title_zh"] = title_zh
    data["info"]["sub_title_zh"] = sub_title_zh
    # original fields untouched aside from added keys
    text = json.dumps(data, ensure_ascii=False, indent=4) + "\n"
    # codepoint audit for AYA inside output
    if AYA not in text and FULL not in text:
        pass
    for ch in text:
        if ch == "\u7dbe":  # 綾 traditional must not appear in zh fields; may appear in source text
            pass
    outp.write_text(text, encoding="utf-8")
    back = json.loads(text)
    src_back = json.loads((SRC / filename).read_text(encoding="utf-8"))
    if len(back["entry"]) != len(src_back["entry"]):
        raise SystemExit("count drift")
    for a, b in zip(src_back["entry"], back["entry"]):
        if a["text"] != b["text"] or a["narrator"] != b["narrator"] or a["location"] != b["location"]:
            raise SystemExit("source field changed")
        if b["zh"] == "":
            raise SystemExit("empty zh after write")
        if AYA in b["zh"] and [ord(c) for c in AYA] != [0x7EEB, 0x6C34]:
            raise SystemExit("aya codepoint")
    print("WROTE", filename, len(entries))


def main() -> None:
    path = Path(sys.argv[1])
    pack = json.loads(path.read_text(encoding="utf-8"))
    apply(pack["file"], pack["title_zh"], pack["sub_title_zh"], pack["zhs"])


if __name__ == "__main__":
    main()
