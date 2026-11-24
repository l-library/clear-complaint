"""Duration compatibility and missing-field recovery use synthetic inputs only."""

import pytest

from app.episode.clarification import canonical_duration, pending_fields


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("两天", "两天"),
        ("一周", "一周"),
        ("3天", "三天"),
        ("1 周", "一周"),
        ("1–3 天", "一至三天"),
        ("4–7 天", "四至七天"),
        ("不到 1 天", "不到一天"),
        ("1 周以上", "一周以上"),
        ("0.5 天", "0.5天"),
        ("不确定", "不确定"),
    ],
)
def test_duration_preserves_ranges_and_qualifiers(raw: str, expected: str) -> None:
    assert canonical_duration(raw) == expected


def test_missing_medication_is_still_asked_after_five_questions() -> None:
    result: dict[str, object] = {
        "status": "insufficient_evidence",
        "missing_fields": ["duration", "medication"],
        "unknown_fields": [],
    }
    assert pending_fields(result, {"duration_text": "1–3 天"}) == ["medication"]


def test_explicit_unknown_and_known_answers_are_not_repeated() -> None:
    result: dict[str, object] = {
        "missing_fields": ["duration", "medication", "location"],
        "unknown_fields": ["location"],
    }
    assert pending_fields(result, {"duration_text": "unknown", "medications_text": "没用药"}) == []


def test_no_evidence_without_missing_fields_does_not_invent_questions() -> None:
    assert pending_fields({"status": "insufficient_evidence", "missing_fields": []}, {}) == []


def test_free_text_and_dates_are_preserved() -> None:
    assert canonical_duration("2026-11-20开始，到现在还没好") == "2026-11-20开始，到现在还没好"
