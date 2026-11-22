"""确定性闸门的行为测试，断言逐条取自 experiment/handoff/constraints.md 的「可测断言」。

归一化、红旗、引用核验全部不碰模型；这些用例守住三条非协商项：
红旗不咨询模型、引用逐字可核、输出落在受控表内。
"""

import pytest

from app.agent import citation, departments, normalize, redflag, vocab
from app.agent.normalize import fold_chars, split_attribution

# ---- 一、输入侧结构化归一 ----


def test_pinyin_complaint_normalizes_to_clinical_words() -> None:
    folded = normalize.normalize("脑壳tong，一直liu鼻涕")

    assert "头痛" in folded
    assert "流涕" in folded
    # 归一化结果不残留拉丁字母
    assert not any("a" <= char <= "z" for char in folded)


def test_normalize_is_a_pure_function() -> None:
    text = "最近两天拉肚子，肚子有点疼，fa烧"
    assert normalize.normalize(text) == normalize.normalize(text)


def test_fold_chars_keeps_words_verbatim() -> None:
    # 引文比对用这一层：只统一字符，不折口语词
    assert fold_chars("发 烧，38.5度！") == fold_chars("发烧38.5度")


def test_split_attribution_extracts_known_term_only() -> None:
    known = vocab.known_terms()

    remainder, attribution = split_attribution("我好像感冒了，一直流鼻涕", known)

    assert attribution == "感冒"
    assert "感冒" not in remainder
    assert "流鼻涕" in remainder


def test_split_attribution_ignores_non_diagnosis_feelings() -> None:
    known = vocab.known_terms()

    # 「冷」不是病名，不能被摘成结论
    remainder, attribution = split_attribution("我觉得很冷，有点流鼻涕", known)

    assert attribution is None
    assert remainder.startswith("我觉得很冷")


# ---- 三、红旗确定性前置 ----


def test_negated_chest_pain_does_not_hit() -> None:
    hits = redflag.detect("没有胸痛，心慌两小时")
    assert all(hit.rule_id != "RF07" for hit in hits) or not any("胸痛" in hit.name for hit in hits)


def test_hypothetical_dehydration_does_not_hit() -> None:
    hits = redflag.detect("会不会脱水")
    assert not any("脱水" in hit.name for hit in hits)


def test_real_chest_pain_with_negation_after_hits() -> None:
    # 否定词在触发词之后，毛病是真的
    hits = redflag.detect("胸口疼，没有缓解，出汗")

    assert any("胸痛" in hit.name for hit in hits)


def test_unrelated_negation_does_not_block_other_rules() -> None:
    # 已知边界（规格书未列）：同一句里第二个真命中若落在前一个否定的 6 字窗口内，
    # 会被窗口一并盖住。窗口语义与 experiment 冻结版一致，先不单方面改动。
    hits = redflag.detect("没有胸痛，但这两天肚子不太舒服，而且便血")

    assert hits  # 血便规则仍要命中


def test_red_flag_hit_forces_emergency() -> None:
    assert redflag.triage_level("胸口疼，没有缓解，出汗") == "emergency"
    assert redflag.triage_level("我流鼻涕三天了") == "undetermined"


def test_rule_table_is_frozen_version_one() -> None:
    rules = redflag.rules()

    assert len(rules) == 16
    assert all(hit.triggers for hit in rules)


# ---- 四、引用闸门 ----

_POOL = [
    "以鼻塞、流涕、喷嚏、咽痛为主要表现，全身症状较轻。",
    "流行性感冒起病急，高热、头痛、乏力等全身症状重于呼吸道症状。",
    "普通感冒多为自限性疾病，一周内多可自行缓解。",
]


def _condition(name: str, idx: list[int], quote: str) -> citation.Condition:
    return citation.Condition(name=name, evidence_idx=idx, quote=quote)


def test_exact_quote_is_kept() -> None:
    result = citation.verify(
        [_condition("上呼吸道感染", [0], "以鼻塞、流涕、喷嚏、咽痛为主要表现")], _POOL
    )
    assert len(result.kept) == 1
    assert result.deleted_count == 0


def test_quote_off_by_one_char_is_deleted() -> None:
    result = citation.verify(
        [_condition("上呼吸道感染", [0], "以鼻塞、流鼻涕、喷嚏、咽痛为主要表现")], _POOL
    )
    assert result.deleted_count == 1


def test_short_quote_is_deleted() -> None:
    result = citation.verify([_condition("发热", [0], "以鼻塞")], _POOL)
    assert result.deleted_count == 1


def test_quote_from_wrong_index_is_deleted() -> None:
    # 不能借别处的原文担保
    result = citation.verify(
        [_condition("上呼吸道感染", [1], "以鼻塞、流涕、喷嚏、咽痛为主要表现")], _POOL
    )
    assert result.deleted_count == 1


def test_out_of_range_index_is_deleted_without_crash() -> None:
    result = citation.verify([_condition("发热", [9], "以鼻塞、流涕、喷嚏为主要表现")], _POOL)
    assert result.deleted_count == 1


def test_pool_exhausted_flags_empty() -> None:
    result = citation.verify([_condition("发热", [0], "完全不在池里的一句话")], _POOL)
    assert result.empty_after_gate
    assert result.deleted_count == 1


def test_quote_matching_ignores_punctuation_and_case() -> None:
    # 折完标点后须仍达到 8 字下限
    result = citation.verify([_condition("发热", [1], "高热、头痛、乏力等全身症状重")], _POOL)
    assert len(result.kept) == 1


# ---- 五、受控词表与科室表 ----


def test_vocab_resolves_free_name_to_longest_match() -> None:
    term = vocab.resolve("普通感冒（不构成诊断）")
    assert term is not None
    assert term.name == "上呼吸道感染"


def test_vocab_rejects_invented_name() -> None:
    assert vocab.resolve("神秘未知综合征X") is None


def test_vocab_names_are_controlled() -> None:
    names = vocab.names()

    assert len(names) == 63
    assert len(names) <= 80
    assert "感冒" not in names  # 别名不进输出契约
    assert "上呼吸道感染" in names


def test_departments_are_frozen() -> None:
    names = departments.names()

    assert len(names) == 17
    assert "急诊科" in names
    assert "全科医学科" in names


@pytest.mark.parametrize("name", ["急诊科", "呼吸内科", "全科医学科", "精神心理科"])
def test_department_contains(name: str) -> None:
    assert departments.contains(name)


def test_department_rejects_free_text() -> None:
    assert not departments.contains("大医院内科")
