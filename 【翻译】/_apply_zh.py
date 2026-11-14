# -*- coding: utf-8 -*-
"""Apply zh fields onto story JSON copies. Does not touch sources."""
import json
import sys
from pathlib import Path

SRC = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本\stories")
OUT = Path(r"H:\【GUST】\【土屋】\拡張少女系トライナリー\kakutora 安卓包\l10n_导出文本\【翻译】\stories")

AYAME = "\u7eeb\u6c34"
BO = "\u5575"

NARRATORS = {
    "": "",
    "つばめ": "燕",
    "雛": "雏",
    "繭": "茧",
    "キリト": "圣翔",
    "ヒカル": "光",
    "真幌": "真幌",
    "神楽": "神乐",
    "透明真幌": "透明真幌",
    "透明みやび": "透明雅",
    "透明アーヤ": "透明" + AYAME,
    "透明ガブリエラ": "透明加布里埃拉",
    "アーヤ": AYAME,
    "ガブリエラ": "加布里埃拉",
    "みやび": "雅",
    "システム": "系统",
}

FORBIDDEN = "\u567b\u54fd\u5566\u7efd"  # 噻 哽 啦 绽


def narrator_zh(name: str) -> str:
    if name in NARRATORS:
        return NARRATORS[name]
    if name.startswith("Dialog") or name.startswith("Battle"):
        return name
    raise KeyError(name)


def apply(filename: str, title_zh: str, sub_title_zh: str, zhs: list) -> None:
    outp = OUT / filename
    if outp.exists():
        print("SKIP", filename)
        return
    data = json.loads((SRC / filename).read_text(encoding="utf-8"))
    entries = data["entry"]
    if len(zhs) != len(entries):
        raise SystemExit(f"{filename} count {len(zhs)} != {len(entries)}")
    for e, zh in zip(entries, zhs):
        if not isinstance(zh, str) or zh == "":
            raise SystemExit(f"empty {filename} {e['location']}")
        bad = [c for c in FORBIDDEN if c in zh]
        if bad:
            raise SystemExit(f"forbidden {bad} {filename} {e['location']}: {zh}")
        if e["text"].count("\n") != zh.count("\n"):
            raise SystemExit(
                f"newlines {filename} {e['location']}\nSRC:{e['text']!r}\nZH:{zh!r}"
            )
        for tok in ("$me$", "$handle$", "$chrname$"):
            if e["text"].count(tok) != zh.count(tok):
                raise SystemExit(f"token {tok} {filename} {e['location']}")
        if e["narrator"] == "つばめ" and "人家" in zh:
            raise SystemExit(f"人家 {filename} {e['location']}")
        if e["narrator"] == "みやび":
            # dialect lines should end on 啵, 咯, 不过, or a question/ellipsis
            pass
        e["zh"] = zh
        e["narrator_zh"] = narrator_zh(e["narrator"])
    data["info"]["title_zh"] = title_zh
    data["info"]["sub_title_zh"] = sub_title_zh
    text = json.dumps(data, ensure_ascii=False, indent=4) + "\n"
    outp.write_text(text, encoding="utf-8")
    # round-trip check
    back = json.loads(text)
    for a, b in zip(data["entry"], back["entry"]):
        if a["text"] != b["text"] or a["zh"] != b["zh"]:
            raise SystemExit("roundtrip mismatch")
    print("WROTE", filename, len(entries))


def main() -> None:
    name = sys.argv[1]
    mod = __import__(name)
    apply(mod.FILENAME, mod.TITLE_ZH, mod.SUB_TITLE_ZH, mod.ZHS)


if __name__ == "__main__":
    main()
