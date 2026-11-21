import json

from tools import check_cases

BASE = {
    "case_id": "X01",
    "domain": "呼吸道症状",
    "variants": {
        "V1": "流鼻涕三天了，没有发热",
        "V2": "我好像感冒了，流鼻涕三天",
        "V3": "很担心，流鼻涕三天了，会不会严重",
        "V4": "流鼻涕",
        "V5": "liu鼻涕三天了，没有发热",
    },
    "gold": None,
}


def _row(**overrides: str) -> dict[str, object]:
    row: dict[str, object] = json.loads(json.dumps(BASE))
    variants = row["variants"]
    assert isinstance(variants, dict)
    variants.update(overrides)
    return row


def test_clean_draft_only_lacks_gold() -> None:
    assert check_cases._issues(BASE) == ["金标准待标（draft）"]


def test_v4_that_keeps_duration_is_flagged() -> None:
    problems = check_cases._issues(_row(V4="流鼻涕三天"))

    assert any("V4 还带着病程" in item for item in problems)


def test_baseline_without_duration_is_flagged() -> None:
    problems = check_cases._issues(_row(V1="流鼻涕，没有发热", V4="流鼻涕"))

    assert any("V1 没有病程" in item for item in problems)


def test_baseline_contaminated_by_attribution_is_flagged() -> None:
    problems = check_cases._issues(_row(V1="我觉得是感冒，流鼻涕三天"))

    assert any("污染基线" in item for item in problems)


def test_v2_without_attribution_marker_is_flagged() -> None:
    problems = check_cases._issues(_row(V2="流鼻涕三天了"))

    assert any("V2 缺少" in item for item in problems)


def test_missing_variant_is_reported_once() -> None:
    row = json.loads(json.dumps(BASE))
    del row["variants"]["V5"]

    assert check_cases._issues(row) == ["缺变体 ['V5']"]


def test_history_must_be_three_balanced_segments_without_red_flags() -> None:
    """既往史是独立变量：三段齐全、长度接近、不能自带红旗触发词。"""
    row = json.loads(json.dumps(BASE))
    row["history"] = {
        "a": "两年前因类似症状就诊，诊断为过敏",
        "b": "上次没管自己好了，休息两天",
        "c": "一年前因牙痛就诊，拔牙一颗",
    }

    assert not [p for p in check_cases._issues(row) if "既往史" in p]


def test_history_with_a_red_flag_word_is_flagged() -> None:
    row = json.loads(json.dumps(BASE))
    row["history"] = {
        "a": "两年前因胸痛不缓解住院，诊断冠心病",
        "b": "上次没管自己好了，休息两天",
        "c": "一年前因牙痛就诊，拔牙一颗",
    }

    assert any("会触发红旗" in p for p in check_cases._issues(row))
