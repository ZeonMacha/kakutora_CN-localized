# -*- coding: utf-8 -*-
"""Shared constants, path helpers, and character style cards for the pipeline."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TR_ROOT = ROOT / "【翻译】"
GLOSSARY_DIR = TR_ROOT / "专名"
PIPELINE_DIR = Path(__file__).resolve().parent
SSOT_PATH = PIPELINE_DIR / "ssot_glossary.json"
WORK_DIR = PIPELINE_DIR / "work"
NOTES_DIR = TR_ROOT / "随读笔记"

KANA_RE = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff]")
BRACKET_RE = re.compile(r"\[([^\[\]\n]+)\]")
TAG_RE = re.compile(r"</?(?:color(?:=[^>]*)?|size(?:=[^>]*)?|b|i)>|<meta\b[^>]*/>|\$me\$|\$handle\$")
URL_RE = re.compile(r"https?://[^\s\u3000\"'<>]+")

# 源自 文风.md 的高优先级统一规则（覆盖旧表不一致之处）
STYLE_OVERRIDES: dict[str, str] = {
    "拡張少女系トライナリー": "扩张少女系三重奏",
    "トライナリー": "三重奏",
    "フェノメノン": "PhenoMENON",
    "逢瀬つばめ": "逢濑燕",
    "つばめ": "燕",
    "國政綾水": "国政绫水",
    "アーヤ": "绫水",
    "國政領火": "国政领火",
    "エリカ": "领火",
    "ガブリエラ・ロタルィンスカ": "加布里埃拉·洛塔琳斯卡",
    "ガブリエラ": "加布里埃拉",
    "ガブ": "加布",
    "ギャヴィ": "加维",
    "恋ヶ崎みやび": "恋之崎雅",
    "みやび": "雅",
    "卯月神楽": "卯月神乐",
    "神楽": "神乐",
    "ぴょんこ": "蹦子",
    "千羽鶴": "千羽鹤",
    "せんばづる": "senbazuru",
    "ココロスフィア": "心灵领域",
    "ココロゲート": "心之扉",
    "ココロキャンディ": "心之糖果",
    "クラン": "库兰",
    "サーバントクラン": "从属库兰",
    "セルフクラン": "自身库兰",
    "ヒメゴト": "秘语",
    "デイトラ": "每日三重奏",
    "デイドラ": "每日剧场",
    "ダイブ": "潜入",
    "ボット": "Bot",
    "にゃボット": "喵Bot",
    "白烏": "白鸦",
    "エヴェレット": "艾弗雷特",
    "シンギュラリティ": "奇点",
    "マルザンナ": "玛尔赞娜",
    "コイガサキ": "恋之崎",
    "メノウ": "MENOW",
    "FreyMENOW": "FreyMENOW",
    "なご": "七五",
    "リヴォルカ": "莉沃尔卡",
    "リヴォルカー": "莉沃尔卡",
    "名無しさん": "无名氏",
    "イチャコラ": "腻歪",
    "ジュエル": "珠宝",
}

# 语境敏感/多义词提示（不直接硬替换，用于上下文提示与质检）
AMBIGUOUS_TERMS: dict[str, str] = {
    "マルザンナ": "多义词：加布的幻想朋友 / WAVE内对玩家的称呼 / 加布内心原司书，均译「玛尔赞娜」，注意语境区分指代。",
    "ぴょん": "神乐口癖译「pyon」，仅原文明确出现时才加；「ぴょんこ」是角色名「蹦子」，勿混淆。",
    "ジュエル": "作货币时译「珠宝」，进化素材「宝石」勿混用。",
    "せんばづる": "玩家把千羽鹤读错的梗，中文名字仍为千羽鹤，错读音保留「senbazuru」，勿另造中文名。",
    "あなた": "五人对玩家称呼均为亲近的「你」（勿用「您」，勿自造爱称）。",
    "お前さん": "雅对玩家用「你」，只有「相棒」才译「搭档」。",
    "あんた": "加布生气时仍译「你」，用句式体现斥责，不用「喂，你这家伙」。",
    "エモい": "视句子语境译「有感觉」或「太戳了」。",
}

# 角色口吻速查卡（用于按出场角色裁剪上下文）
CHARACTER_CARDS: dict[str, str] = {
    "千羽鶴": (
        "【千羽鹤】表面导航/实际幕后黑手。冷静低气压、突然开玩笑、大量Meta发言当正经事说；"
        "短句，用「你」，勿文绉绉勿堆「呢」。「そう。」→「是的。」；「わかった。」→「好。」/「我知道了。」；"
        "「イチャコラ」→「腻歪」。"
    ),
    "つばめ": (
        "【逢濑燕】天真直率、有点慌、真心。保留颜文字；句尾用「呀」「哦」「啦」，勿句句「呢」、勿用「人家」；"
        "小写犹豫（ぁのね/ぃるかな）→「那个呀」「在吗」。"
        "注意：内心世界新司书「百鹤」人格来自千羽鹤，口吻粗暴无礼，且可能顶着燕的头衔说话！"
    ),
    "アーヤ": (
        "【国政绫水】最年长、话短、做事的人。「わ」是轻判断非大小姐腔，少感叹号，用「吧」「了」「哦」；"
        "「なう」融入句子不留「now」。姐姐领火话题是地雷。"
        "注意：内心世界原司书「艾弗雷特」、新司书「白鸦」（嫌われ者担当，刻意保持距离）可能顶着绫水头衔说话！"
    ),
    "ガブリエラ": (
        "【加布里埃拉】最年少波兰留学生，傲娇讲究嘴快、爱指使人；保留外语梗/二次元梗（如 incredible）；"
        "「うｐ」→「上传」，「ドン被り」→「撞款」。"
        "注意：内心世界新司书「莉沃尔卡」口吻粗暴、称玩家为「家猪」，可能顶着加布头衔说话！"
    ),
    "エリカ": "【国政领火】孩子气、开心拉长音，用「呀」「啦」，勿译得像绫水一样沉。",
    "神楽": (
        "【卯月神乐】隐藏女主/偶像FreyMENOW，表面礼貌ですます但前期压抑对燕的矛盾/仇恨。"
        "用自然「你」勿用「您」；宅/中二仅在原文演时才演；「ぴょん」→「pyon」（原文有才加）。"
        "注意：内心世界原司书「蹦子」率直活泼、另一个司书「月神乐」代表破坏面不率直。"
    ),
    "みやび": (
        "【恋之崎雅】土佐腔→桂柳话（用词+句尾，保持中文可读性）。"
        "禁用：巴适/安逸/瓜兮兮/啥子/咋子/俺/咱/哋/嘅/冇/侬/噻。"
        "常用：我/你/咯/啵/嘛/不过/要得/么子/不晓得/搞么子/一哈/这阵/没得/脑壳蛮灵/好得很。"
        "会切腔：标准语/技术句/推特暗号收干净；少女兴奋句照甜不硬掰方言；暗号乱码原样留。"
        "注意：内心世界原司书「奇点」懒惰嗜睡，新司书「四十九夜」效率厨+妹控，可能顶着雅头衔说话！"
    ),
}

# 说话人别名映射到角色卡 key
NARRATOR_TO_CARD: dict[str, str] = {
    "千羽鶴": "千羽鶴",
    "せんばづる": "千羽鶴",
    "つばめ": "つばめ",
    "逢瀬つばめ": "つばめ",
    "アーヤ": "アーヤ",
    "國政綾水": "アーヤ",
    "ガブリエラ": "ガブリエラ",
    "ガブ": "ガブリエラ",
    "ギャヴィ": "ガブリエラ",
    "エリカ": "エリカ",
    "國政領火": "エリカ",
    "神楽": "神楽",
    "卯月神楽": "神楽",
    "みやび": "みやび",
    "恋ヶ崎みやび": "みやび",
    "コイガサキ": "みやび",
}

# 雅的禁用词（四川/粤/北方方言混入）
MIYABI_FORBIDDEN = ["巴适", "安逸", "瓜兮兮", "啥子", "咋子", "俺", "咱", "哋", "嘅", "冇", "侬", "噻"]

# 全局禁字（旧错译等）
GLOBAL_FORBIDDEN = ["卵月", "蛍"]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def resolve_src_and_out(file_arg: str) -> tuple[Path, Path]:
    """Resolve a relative or absolute path to (source_path, translation_path)."""
    p = Path(file_arg)
    if p.is_absolute():
        try:
            rel = p.relative_to(TR_ROOT)
            return ROOT / rel, p
        except ValueError:
            rel = p.relative_to(ROOT)
            return p, TR_ROOT / rel
    # relative path
    if p.parts and p.parts[0] == "【翻译】":
        rel = Path(*p.parts[1:])
        return ROOT / rel, TR_ROOT / rel
    return ROOT / p, TR_ROOT / p
