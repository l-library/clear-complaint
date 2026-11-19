"""引用闸门：只许引用本轮检索池的下标，且引文要与池内原文逐字对得上。

能证明什么要说清楚：它证明引用确实来自本轮检索结果、且文字一致；不证明结论与
引文在语义上相符。后者靠输出结构约束与人工抽查，材料里不要写成「做了语义核验」。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from harness.normalize import fold_chars

# 匹配段下限。低于 8 字，「发热」「头痛」这种词轻松过关，闸门形同虚设。
MIN_MATCH_CHARS = 8


@dataclass
class Condition:
    """一条「可能相关情况」。quote 是模型声称摘自检索池的那句原文。

    只核病名不核引文，等于没核：病名是模型自己写的，池子里有没有它无关紧要。
    """

    name: str
    evidence_idx: list[int]
    quote: str = ""


@dataclass
class GateResult:
    kept: list[Condition] = field(default_factory=list)
    deleted: list[Condition] = field(default_factory=list)
    empty_after_gate: bool = False

    @property
    def deleted_count(self) -> int:
        return len(self.deleted)


def _matches(quote: str, content: str) -> bool:
    """归一化后做子串匹配，并要求匹配段达到最小长度。

    比较用字符层归一（全半角、空白、标点），不折同义词：把「发烧」放宽成「发热」
    会让「逐字核验」变成「逐意核验」，那这条约束就不再可证了。
    """
    folded_quote = fold_chars(quote)
    folded_content = fold_chars(content)
    if len(folded_quote) < MIN_MATCH_CHARS:
        return False
    return folded_quote in folded_content


def verify(conditions: list[Condition], pool: list[str]) -> GateResult:
    """逐条核验。索引越界、无引用、引文对不上，一律删掉这条候选。"""
    result = GateResult()
    for condition in conditions:
        in_range = bool(condition.evidence_idx) and all(
            0 <= index < len(pool) for index in condition.evidence_idx
        )
        # 引文必须落在它自己引用的那些片段里，不能借别处的原文来担保
        cited = [pool[index] for index in condition.evidence_idx if index < len(pool)]
        ok = in_range and any(_matches(condition.quote, content) for content in cited)
        (result.kept if ok else result.deleted).append(condition)
    result.empty_after_gate = not result.kept
    return result
