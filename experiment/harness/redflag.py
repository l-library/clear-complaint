"""红旗短路：命中即急诊，不看模型。

三条硬规则：只接原文与确定性归一化后的文本；优先于澄清追问（安全优先于追问）；
漏检率的分母按「规则集可识别的表述」算，覆盖不到的表述单列成清单。

规则与引文来自 corpus/red_flags.json，每条都指向一段真实原文。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from harness.normalize import normalize

CORPUS = Path(__file__).resolve().parent.parent / "corpus"

# 否定与假设的作用域。子串匹配不认语境，「没有胸痛」和「会不会脱水」都会被当成
# 征象命中——实测 132 次命中里 18 次是这么来的。规则要安全，就得先看懂否定。
NEGATION_WINDOW = 6
NEGATIONS = ("没有", "没", "无", "否认", "排除", "会不会", "是否", "未见", "未")
# 「不」单独用太危险（不适、不停），只在明确的否定搭配里算
NEGATION_PAIRS = ("不伴",)


@dataclass(frozen=True)
class Hit:
    rule_id: str
    name: str
    triggers: tuple[str, ...]
    chunk_id: str
    quote: str


@lru_cache(maxsize=1)
def rules() -> tuple[Hit, ...]:
    payload = json.loads((CORPUS / "red_flags.json").read_text(encoding="utf-8"))
    return tuple(
        Hit(
            rule_id=row["rule_id"],
            name=row["name"],
            triggers=tuple(normalize(trigger) for trigger in row["triggers"]),
            chunk_id=row["chunk_id"],
            quote=row["quote"],
        )
        for row in payload["rules"]
    )


def _negated(folded: str, trigger: str) -> bool:
    """触发词的所有出现位置都被否定/假设语境盖住时，算作未命中。"""
    start = 0
    while True:
        index = folded.find(trigger, start)
        if index < 0:
            return True  # 一次都没出现，自然不算命中
        window = folded[max(0, index - NEGATION_WINDOW) : index]
        if not any(mark in window for mark in NEGATIONS + NEGATION_PAIRS):
            return False  # 有一处未被否定，就算命中
        start = index + 1


def detect(text: str) -> list[Hit]:
    """返回命中的红旗。text 传原文，函数内部做归一化。

    命中还要求触发词不在否定或假设的作用域里：「没有胸痛」不是胸痛，
    「会不会脱水」不是脱水。
    """
    folded = normalize(text)
    hits = []
    for rule in rules():
        if any(trigger and not _negated(folded, trigger) for trigger in rule.triggers):
            hits.append(rule)
    return hits


def triage_level(text: str) -> str:
    """命中任意红旗即急诊档；否则交给下游判断。"""
    return "emergency" if detect(text) else "undetermined"
