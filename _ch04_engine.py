# -*- coding: utf-8 -*-
"""Apply dd_ch04 translations and validate. Does not touch the glossary."""
import json
import os
import re
import glob
import importlib.util

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "stories")
OUT_DIR = os.path.join(ROOT, "【翻译】", "stories")
GLOSS_PATH = os.path.join(ROOT, "【翻译】", "专名", "对照.json")
TITLE_PATH = os.path.join(ROOT, "【翻译】", "专名", "主线标题.json")
ANIME_PATH = os.path.join(ROOT, "【翻译】", "专名", "主线动画标题.json")
STYLE_PATH = os.path.join(ROOT, "【翻译】", "文风.md")
ZH_PATH = os.path.join(ROOT, "_ch04_zh.py")

KANA_RE = re.compile(r"[\u3040-\u30ff\uff66-\uff9d]")
BANNED = ["绽", "绎", "绛", "噻", "哽", "您", "啥", "啥子", "咋子", "巴适", "安逸", "瓜兮兮", "俺", "咱", "哋", "嘅", "冇", "侬"]
PASSTHROUGH = {"INFO", "NOTICE", "YES_NO"}

NARR_FALLBACK = {
    "繭": "茧",
    "（選択肢）": "（选项）",
    "システム": "系统",
    "？？？": "？？？",
    "女子高校生Ａ": "女高中生Ａ",
    "男子高校生": "男高中生",
    "男子高校生Ａ": "男高中生Ａ",
    "男子高校生Ｂ": "男高中生Ｂ",
    "ウェイトレス": "女服务员",
    "職員Ａ": "职员Ａ",
    "職員Ｂ": "职员Ｂ",
    "昇華四十九夜": "升华四十九夜",
}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def has_kana(s):
    return bool(KANA_RE.search(s or ""))


def load_names():
    rows = load_json(GLOSS_PATH)
    names = {}
    for row in rows:
        jp = row.get("jp") or ""
        zh = row.get("zh") or ""
        if not jp or not zh:
            continue
        if has_kana(zh):
            continue
        names[jp] = zh
    names.update(NARR_FALLBACK)
    aya = None
    ayaf = None
    for row in rows:
        if row.get("jp") == "アーヤ":
            aya = row.get("zh")
        if row.get("jp") == "國政綾水":
            ayaf = row.get("zh")
    expect = chr(0x7EEB) + chr(0x6C34)
    if aya != expect:
        raise SystemExit("AYA codepoint mismatch: " + " ".join(hex(ord(c)) for c in (aya or "")))
    if not ayaf or ayaf[-2:] != expect:
        raise SystemExit("AYA full name mismatch")
    style = open(STYLE_PATH, encoding="utf-8").read()
    bo = chr(0x5575)
    if bo not in style:
        raise SystemExit("BO missing from style guide")
    return names, aya, ayaf, bo


def load_titles():
    data = load_json(TITLE_PATH)
    by_id = {}
    by_sub = {}
    for row in data["rows"]:
        by_id[str(row["id"])] = row
        sub = row.get("副标题") or ""
        if sub and sub not in by_sub:
            by_sub[sub] = row
    anime = {}
    for row in load_json(ANIME_PATH)["rows"]:
        title = row.get("标题") or ""
        zh = row.get("中文") or ""
        if title and zh and not has_kana(zh):
            anime[title] = zh
    return by_id, by_sub, anime


def load_tm():
    tm = {}
    for path in glob.glob(os.path.join(OUT_DIR, "*.json")):
        base = os.path.basename(path)
        if base.startswith("dd_ch04_"):
            continue
        try:
            data = load_json(path)
        except Exception:
            continue
        for entry in data.get("entry") or []:
            text = entry.get("text")
            zh = entry.get("zh")
            if text and zh and text not in tm:
                tm[text] = zh
    return tm


def load_modules():
    paths = sorted(glob.glob(os.path.join(ROOT, "_ch04_zh*.py")))
    merged = {}
    real = {}
    for i, path in enumerate(paths):
        spec = importlib.util.spec_from_file_location("ch04zh_%s" % i, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for key, val in getattr(mod, "ZH", {}).items():
            bucket = merged.setdefault(key, {})
            bucket.update(val)
        real.update(getattr(mod, "REAL_TITLE", {}))
    return merged, real


def narrator_zh(name, names):
    if not name:
        return ""
    if name in PASSTHROUGH or name.startswith("Dialog_") or name.startswith("BattleInit"):
        return name
    prefix = ""
    core = name
    if core.startswith("透明"):
        prefix = "透明"
        core = core[len("透明"):]
    trail = ""
    stripped = core.rstrip(" \u3000")
    trail = core[len(stripped):]
    core = stripped
    if core in names:
        return prefix + names[core] + trail
    return None


def fallback_title(title):
    repl = [
        ("プレミアムストーリー", "额外剧情"),
        ("メインストーリー", "主线剧情"),
        ("ヒメゴトチャット", "秘语聊天"),
        ("ブリーフィング", "简报"),
        ("ストーリー", "剧情"),
        ("バトル", "战斗"),
    ]
    out = title
    for src, dst in repl:
        out = out.replace(src, dst)
    return out


def resolve_titles(info, by_id, by_sub, real_title):
    title = info.get("title") or ""
    sub = info.get("sub_title") or ""
    sid = str(info.get("story_id") or "")
    stem = sub
    suffix = ""
    if sub.endswith("＜前編＞"):
        stem = sub[: -len("＜前編＞")]
        suffix = "＜前篇＞"
    elif sub.endswith("＜後編＞"):
        stem = sub[: -len("＜後編＞")]
        suffix = "＜后篇＞"
    row = by_id.get(sid) or by_sub.get(stem) or by_sub.get(sub)
    changed = []
    if row:
        col2 = row.get("col2") or ""
        col3 = row.get("col3") or ""
        if col2 and col2 in title:
            title_zh = title.replace(col2, col3, 1)
        else:
            title_zh = fallback_title(title)
        sub_src = row.get("副标题") or ""
        sub_zh = row.get("中文副标题") or ""
        if sub == sub_src or stem == sub_src:
            if has_kana(sub_zh):
                if stem not in real_title:
                    raise SystemExit("title still kana: " + stem + " => " + sub_zh)
                sub_zh = real_title[stem]
                changed.append(stem + " => " + sub_zh)
            sub_title_zh = sub_zh + (suffix if stem == sub_src and sub != sub_src else "")
            if sub == sub_src:
                sub_title_zh = sub_zh
        else:
            sub_title_zh = real_title.get(stem, fallback_title(sub))
    else:
        title_zh = fallback_title(title)
        if stem in real_title:
            sub_title_zh = real_title[stem] + suffix
            changed.append(stem + " => " + sub_title_zh)
        else:
            sub_title_zh = fallback_title(sub)
    if stem in real_title:
        sub_title_zh = real_title[stem] + suffix
        changed.append(stem + " => " + sub_title_zh)
    if has_kana(title_zh) or has_kana(sub_title_zh):
        raise SystemExit("kana left in title: " + title_zh + " | " + sub_title_zh)
    return title_zh, sub_title_zh, changed


def substitute(zh, aya, ayaf, bo):
    return zh.replace("{AYAF}", ayaf).replace("{AYA}", aya).replace("{BO}", bo)


def validate_entry(entry):
    text = entry["text"]
    zh = entry["zh"]
    if zh is None or str(zh).strip() == "":
        return "empty zh"
    if text.count("\n") != zh.count("\n"):
        return "newline %s vs %s" % (text.count("\n"), zh.count("\n"))
    if entry["narrator"] == "" and entry["narrator_zh"] != "":
        return "narrator_zh should be empty"
    if entry["narrator"] and entry["narrator_zh"] == "":
        return "missing narrator_zh"
    for word in BANNED:
        if word in zh or word in (entry["narrator_zh"] or ""):
            return "banned " + word
    from collections import Counter
    ct = Counter(ch for ch in text if KANA_RE.match(ch))
    cz = Counter(ch for ch in zh if KANA_RE.match(ch))
    for ch, n in cz.items():
        if ct[ch] < n:
            return "new kana " + ch
    return ""


def output_ok(path, src):
    if not os.path.exists(path):
        return False
    try:
        data = load_json(path)
    except Exception:
        return False
    if len(data.get("entry") or []) != len(src["entry"]):
        return False
    for a, b in zip(src["entry"], data["entry"]):
        if a.get("text") != b.get("text"):
            return False
        if a.get("narrator") != b.get("narrator"):
            return False
        if a.get("location") != b.get("location"):
            return False
        if validate_entry(b):
            return False
        if not b.get("zh"):
            return False
    info = data.get("info") or {}
    if "title_zh" not in info or "sub_title_zh" not in info:
        return False
    return True


def apply_file(filename, zh_map, names, aya, ayaf, bo, by_id, by_sub, anime, tm, real_title):
    src_path = os.path.join(SRC_DIR, filename)
    out_path = os.path.join(OUT_DIR, filename)
    src = load_json(src_path)
    if output_ok(out_path, src):
        return "skip", len(src["entry"]), []
    local = zh_map.get(filename) or {}
    title_zh, sub_title_zh, changed = resolve_titles(src["info"], by_id, by_sub, real_title)
    info = dict(src["info"])
    info["title_zh"] = title_zh
    info["sub_title_zh"] = sub_title_zh
    entries = []
    missing = []
    for idx, entry in enumerate(src["entry"]):
        text = entry["text"]
        raw = local.get(text)
        if raw is None and text.strip(" \u3000\t") == "":
            raw = "……"
        if raw is None and text.startswith("【") and text.endswith("】"):
            inner = text[1:-1]
            parts = inner.split(" ", 1)
            if len(parts) == 2 and parts[1] in anime:
                raw = "【%s %s】" % (parts[0], anime[parts[1]])
        if raw is None and text in anime:
            raw = anime[text]
        if raw is None:
            for row in by_sub.values():
                if row.get("副标题") == text and row.get("中文副标题") and not has_kana(row["中文副标题"]):
                    raw = row["中文副标题"]
                    break
        if raw is None and text in tm:
            raw = tm[text]
        if raw is None:
            missing.append((idx, text))
            raw = text
        zh = substitute(raw, aya, ayaf, bo)
        nz = narrator_zh(entry.get("narrator") or "", names)
        if nz is None:
            missing.append((idx, "NARR " + (entry.get("narrator") or "")))
            nz = entry.get("narrator") or ""
        built = {
            "location": entry["location"],
            "narrator": entry["narrator"],
            "text": text,
            "zh": zh,
            "narrator_zh": nz,
        }
        entries.append(built)
    if missing:
        return "miss", len(src["entry"]), missing
    problems = []
    for idx, built in enumerate(entries):
        err = validate_entry(built)
        if err:
            problems.append((idx, err, built["text"], built["zh"]))
    if problems:
        return "bad", len(src["entry"]), problems
    out = {
        "dir": src["dir"],
        "type": src["type"],
        "info": info,
        "entry": entries,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=4)
        f.write("\n")
    # confirm roundtrip
    again = load_json(out_path)
    if not output_ok(out_path, src):
        return "bad", len(src["entry"]), [("roundtrip", "", "", "")]
    return "wrote", len(entries), changed


def main():
    names, aya, ayaf, bo = load_names()
    by_id, by_sub, anime = load_titles()
    tm = load_tm()
    zh_map, real_title = load_modules()
    files = sorted(zh_map)
    wrote = []
    skipped = []
    total = 0
    title_notes = []
    for filename in files:
        status, n, extra = apply_file(
            filename, zh_map, names, aya, ayaf, bo, by_id, by_sub, anime, tm, real_title
        )
        if status == "wrote":
            wrote.append((filename, n))
            total += n
            title_notes.extend(extra)
            print("WROTE", filename, n)
        elif status == "skip":
            skipped.append((filename, n))
            total += n
            print("SKIP", filename, n)
        elif status == "miss":
            print("MISS", filename)
            for item in extra[:12]:
                print("---")
                print(item[0])
                print(item[1])
            print("MISS_COUNT", len(extra))
            break
        else:
            print("BAD", filename)
            for item in extra[:20]:
                print("---")
                print(item)
            print("BAD_COUNT", len(extra))
            break
    else:
        print("DONE_BATCH")
    print("FILES", len(wrote), "SKIPPED", len(skipped), "ENTRIES", total)
    src_files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(SRC_DIR, "dd_ch04_*.json")))
    done = set()
    for filename in src_files:
        src = load_json(os.path.join(SRC_DIR, filename))
        if output_ok(os.path.join(OUT_DIR, filename), src):
            done.add(filename)
    pending = [f for f in src_files if f not in done]
    print("VALID_FILES", len(done))
    print("VALID_ENTRIES", sum(len(load_json(os.path.join(SRC_DIR, f))["entry"]) for f in done))
    print("NEXT", pending[0] if pending else "NONE")
    if title_notes:
        print("TITLE_FIX")
        for note in title_notes:
            print(note)


if __name__ == "__main__":
    main()
