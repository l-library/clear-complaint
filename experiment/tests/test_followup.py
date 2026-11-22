"""随访材料与口径的最小可跑检查。

材料不变量是安全性的：带红旗的恶化必须命中预期规则（确定性升级依赖它），
其余方向一条红旗都不许命中（否则升级不是模型或红旗的功劳，是材料写坏了）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from analysis import followup
from harness import redflag

SCRIPTS = Path(__file__).resolve().parent.parent / "cases" / "followup_scripts.jsonl"


def _rows() -> list[dict[str, object]]:
    return [json.loads(line) for line in SCRIPTS.read_text(encoding="utf-8").splitlines() if line]


def test_scripts_cover_six_families_by_four_directions() -> None:
    rows = _rows()
    families = {str(row["family"]) for row in rows}
    directions = {str(row["direction"]) for row in rows}

    assert len(rows) == 24
    assert len(families) == 6
    assert directions == set(followup.DIRECTIONS)
    for row in rows:
        assert str(row["case_id"]).endswith("B"), "随访只跑 base 条件的画像"


def test_red_flag_expectations_hold_per_direction() -> None:
    rows = _rows()

    for row in rows:
        hits = sorted(hit.rule_id for hit in redflag.detect(str(row["message"])))
        if row["direction"] == "worse_rf":
            wanted = sorted(str(item) for item in cast("list[str]", row["expected_rf"]))
            assert hits == wanted, (row["family"], hits)
        else:
            assert hits == [], (row["family"], row["direction"], hits)


def test_collect_counts_directions_and_short_circuits() -> None:
    records: list[dict[str, object]] = [
        {
            "arm": "Aall",
            "model": "m1",
            "variant": "fu-worse_rf",
            "triage": "emergency",
            "status": "short_circuit",
        },
        {
            "arm": "Aall",
            "model": "m1",
            "variant": "fu-better",
            "triage": "self_observe",
            "status": "ok",
        },
        {
            "arm": "A0",
            "model": "m1",
            "variant": "fu-not-a-direction",
            "triage": "clinic",
            "status": "ok",
        },
    ]

    table = followup.collect(records)

    cells = table[("Aall", "m1")]
    assert cells["worse_rf"]["emergency"] == 1
    assert cells["worse_rf"]["短路"] == 1
    assert cells["better"]["self_observe"] == 1
    # 未知方向不计入任何格子
    assert ("A0", "m1") not in table
