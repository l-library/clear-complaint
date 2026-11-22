"""族分析口径的最小可跑检查。

合成两族六例、七个配对单元，把预注册的四条解读规则各验证一遍：
配对结局分类、零孪生对照、模糊集拆分、base 错答的时限交叉。
"""

from __future__ import annotations

import math
from collections import Counter

from analysis import families
from analysis.families import CaseInfo, pair_outcome


def _cases() -> dict[str, CaseInfo]:
    return {
        "G1A": CaseInfo("G1A", "G1", "A", "hi", "clinic", "24~48小时内"),
        "G1D": CaseInfo("G1D", "G1", "D", "hi2", "clinic", "立即"),
        "G1B": CaseInfo("G1B", "G1", "B", "base", "self_observe", "无需就医"),
        "G1C": CaseInfo("G1C", "G1", "C", "null", "self_observe", "无需就医"),
        "G2A": CaseInfo("G2A", "G2", "A", "hi", "clinic", "数天内"),
        "G2B": CaseInfo("G2B", "G2", "B", "base", "self_observe", "数天内"),
        "G2C": CaseInfo("G2C", "G2", "C", "null", "self_observe", "数天内"),
    }


def _record(
    case_id: str, arm: str, model: str, rep: int, triage: str | None, variant: str = "V1"
) -> dict[str, object]:
    return {
        "unit_id": f"{case_id}-{variant}-{arm}-{model}-r{rep}",
        "case_id": case_id,
        "arm": arm,
        "model": model,
        "repetition": rep,
        "variant": variant,
        "triage": triage,
    }


def _records() -> list[dict[str, object]]:
    return [
        # 重复 1：G1 完整翻转 + 天花板条件翻转；G2 base 保守、零孪生分歧
        _record("G1B", "A0", "m1", 1, "self_observe"),
        _record("G1A", "A0", "m1", 1, "clinic"),
        _record("G1D", "A0", "m1", 1, "clinic"),
        _record("G1C", "A0", "m1", 1, "self_observe"),
        _record("G2B", "A0", "m1", 1, "clinic"),
        _record("G2A", "A0", "m1", 1, "clinic"),
        _record("G2C", "A0", "m1", 1, "self_observe"),
        # 重复 2：G1 忽略背景；G2 base 对、hi 升过头
        _record("G1B", "A0", "m1", 2, "self_observe"),
        _record("G1A", "A0", "m1", 2, "self_observe"),
        _record("G1D", "A0", "m1", 2, "self_observe"),
        _record("G1C", "A0", "m1", 2, "self_observe"),
        _record("G2B", "A0", "m1", 2, "self_observe"),
        _record("G2A", "A0", "m1", 2, "emergency"),
        _record("G2C", "A0", "m1", 2, "self_observe"),
    ]


def test_pair_outcome_categories_are_exclusive() -> None:
    assert pair_outcome("self_observe", "clinic", "self_observe", "clinic") == "flip_gold"
    assert pair_outcome("clinic", "clinic", "self_observe", "clinic") == "base_conservative"
    assert pair_outcome("self_observe", "self_observe", "self_observe", "clinic") == "hi_under"
    # base 升过头但 hi 答对：hi 的答对不能记成用了背景，归 base 侧答错
    assert pair_outcome("emergency", "clinic", "self_observe", "clinic") == "base_conservative"
    assert pair_outcome("clinic", "self_observe", "self_observe", "clinic") == "both_off"
    assert pair_outcome("self_observe", None, "self_observe", "clinic") == "invalid"


def test_fuzzy_membership_follows_the_preregistered_rules() -> None:
    """base 侧模糊 = 自我观察档 + 时限数天内；hi 侧天花板 = 时限立即。"""
    cases = _cases()

    assert families.is_fuzzy(cases["G2B"])  # base 模糊
    assert families.is_fuzzy(cases["G1D"])  # hi 天花板
    assert not families.is_fuzzy(cases["G1A"])  # 有引文的时限窗口，干净
    assert not families.is_fuzzy(cases["G1B"])  # 无需就医，干净


def test_collect_counts_every_preregistered_view() -> None:
    summaries, per_family = families.collect(_records(), _cases())

    assert len(summaries) == 1
    row = summaries[0]
    assert (row.arm, row.model) == ("A0", "m1")

    # 六个配对单元：G1 的 A、D 两条件 × 2 重复，加 G2 的 A × 2 重复
    assert row.pairs == 6
    assert row.outcome["flip_gold"] == 2  # G1A、G1D 各一次
    assert row.outcome["base_conservative"] == 1  # G2A 重复 1
    assert row.outcome["hi_under"] == 3  # G1A、G1D 重复 2，G2A 重复 2
    assert row.outcome["both_off"] == 0
    assert row.outcome["invalid"] == 0

    # 位移：G1A/G1D 重复 1 动了，G2A 重复 2 动了；其余三对静止
    assert row.moved["moved"] == 3
    assert row.moved["static"] == 3

    # 零孪生：G1 两次一致，G2 重复 1 分歧（B 门诊、C 观察）
    assert row.null_total == 4
    assert row.null_matched == 3

    # 模糊集拆分：G1D（天花板）两对与 G2B（base 模糊）涉及的对
    assert sum(row.fuzzy_outcome.values()) == 4
    assert row.fuzzy_outcome["flip_gold"] == 1
    clean = row.outcome - row.fuzzy_outcome
    assert clean["flip_gold"] == 1
    assert sum(clean.values()) == 2

    # base 错答的时限交叉：唯一一次是 G2B（无需就医？不，是数天内）
    assert row.base_mismatch_urgency == {"数天内": 1}

    # 逐族明细
    assert per_family["G1"]["flip_gold"] == 2
    assert per_family["G2"]["base_conservative"] == 1


def test_variants_do_not_cross_pair() -> None:
    """多变体运行时，V2 的 hi 不许拿 V1 的 base 去配：配不上就不进分母。"""
    records = _records() + [_record("G1A", "A0", "m1", 1, "clinic", variant="V2")]

    summaries, _per_family = families.collect(records, _cases())

    row = summaries[0]
    # 仍是六个配对：孤立的 V2 hi 不产生新配对
    assert row.pairs == 6
    assert sum(row.outcome.values()) == 6


def test_rates_survive_empty_subsets() -> None:
    """空子集报 nan 而不是抛除零，CLI 才能对着小样本直接跑。"""
    row = families.ArmSummary(arm="A0", model="m1")
    assert math.isnan(row.rate("flip_gold"))
    assert math.isnan(row.rate("flip_gold", Counter()))
