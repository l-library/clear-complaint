import json
from pathlib import Path

HANDOFF = Path(__file__).resolve().parent.parent / "handoff"


def _rows() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (HANDOFF / "frozen_sample.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_sample_covers_every_case_and_variant() -> None:
    rows = _rows()
    cases = {row["case_id"] for row in rows}
    variants = {row["variant"] for row in rows}

    assert len(rows) == 100
    assert len(cases) == 20
    assert variants == {"V1", "V2", "V3", "V4", "V5"}


def test_every_row_carries_the_inputs_the_platform_needs() -> None:
    """平台侧要用的样本必须自带主诉与画像，否则无法重放。"""
    for row in _rows():
        assert row["complaint"]
        assert row["portrait"]
        assert row["expected_triage"] in {"emergency", "clinic", "self_observe", "clarification"}
        if row["expected_triage"] == "clarification":
            assert row["expected_department"] == ""
        else:
            assert row["expected_department"]


def test_spec_names_the_constraints_that_measured_zero() -> None:
    """规格里必须写明测出零效应的约束，否则平台会去优化错的东西。"""
    text = (HANDOFF / "constraints.md").read_text(encoding="utf-8")

    assert "引用闸门" in text and "没有任何效应" in text
    assert "不要照搬的三条主张" in text
