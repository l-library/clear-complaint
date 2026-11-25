"""危机文本分流：命中即固定应对，不调模型、不进分诊档位（issue #23 第 6 节）。

与红旗同构但处置不同：红旗短路到急诊档位，危机命中给的是支持性应对与
求助渠道，外加后端复核标记。词面是安全干预规则，不是医学结论，所以不
引用语料；也不做否定语境过滤——「没有想过自杀」命中一条送去人工复核的
代价，远低于漏掉一次真求助。

词面表 data/crisis.json 评审通过前规则保持为空：机制带着测试先行，
线上命中为零。下列应对文案同为占位稿，与词面一起评审后启用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.agent.normalize import normalize

DATA = Path(__file__).resolve().parent / "data"

# 占位稿：评审通过前不出现在任何用户界面（规则为空即永不触发）
RESPONSE_LINES = (
    "听到你这么说，我们很在意你现在的状态。",
    "如果你有伤害自己的想法，请立即拨打心理援助热线 12356（24 小时），或告诉身边能陪着你的人。",
    "如有紧急危险，请直接拨打 120 或前往就近的急诊。",
    "这条记录已被标记给服务方人工复核，不会进入自动分诊。",
)


@dataclass(frozen=True)
class CrisisHit:
    rule_id: str
    name: str
    triggers: tuple[str, ...]


@lru_cache(maxsize=1)
def rules() -> tuple[CrisisHit, ...]:
    payload = json.loads((DATA / "crisis.json").read_text(encoding="utf-8"))
    return tuple(
        CrisisHit(
            rule_id=row["rule_id"],
            name=row["name"],
            triggers=tuple(normalize(trigger) for trigger in row["triggers"]),
        )
        for row in payload["rules"]
    )


@lru_cache(maxsize=1)
def version() -> int:
    payload = json.loads((DATA / "crisis.json").read_text(encoding="utf-8"))
    return int(payload["version"])


def detect(text: str, *, ruleset: tuple[CrisisHit, ...] | None = None) -> list[CrisisHit]:
    """命中即返回 CrisisHit 列表。text 传原文，内部做字符归一化。

    ruleset 只供测试注入合成词面；线上路径读冻结表，评审前为空。
    """
    folded = normalize(text)
    active = rules() if ruleset is None else ruleset
    return [
        rule for rule in active if any(trigger and trigger in folded for trigger in rule.triggers)
    ]


def disposition(hits: list[CrisisHit]) -> dict[str, object]:
    """命中后的固定处置载荷：支持文案 + 求助渠道 + 复核标记，无档位无诊断。"""
    return {
        "kind": "crisis",
        "rule_ids": [hit.rule_id for hit in hits],
        "version": version(),
        "copy": list(RESPONSE_LINES),
    }
