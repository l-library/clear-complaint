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
