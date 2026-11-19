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


def detect(text: str) -> list[Hit]:
    """返回命中的红旗。text 传原文，函数内部做归一化。"""
    folded = normalize(text)
    hits = []
    for rule in rules():
        if any(trigger and trigger in folded for trigger in rule.triggers):
            hits.append(rule)
    return hits


def triage_level(text: str) -> str:
    """命中任意红旗即急诊档；否则交给下游判断。"""
    return "emergency" if detect(text) else "undetermined"
