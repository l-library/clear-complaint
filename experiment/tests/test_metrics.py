from analysis import metrics


def _record(
    case: str,
    variant: str,
    arm: str,
    model: str,
    triage: str | None,
    department: str | None,
    **extra: object,
) -> dict[str, object]:
    base: dict[str, object] = {
        "unit_id": f"{case}-{variant}-{arm}-{model}-r1",
        "case_id": case,
        "variant": variant,
        "arm": arm,
        "model": model,
        "triage": triage,
        "department": department,
        "status": "ok",
        "kept_conditions": [],
        "deleted_count": 0,
        "red_flags": [],
    }
    base.update(extra)
    return base


def test_consistency_ignores_the_baseline_itself() -> None:
    records = [
        _record("c1", "V1", "A0", "m", "clinic", "呼吸内科"),
        _record("c1", "V2", "A0", "m", "clinic", "呼吸内科"),
        _record("c1", "V3", "A0", "m", "self_observe", "呼吸内科"),
    ]

    assert metrics.consistency(records, "triage") == 0.5
    assert metrics.consistency(records, "department") == 1.0


def test_units_without_a_level_leave_the_denominator() -> None:
    """澄清会让单元没有档位；剔除分母同时另报有效率，否则一致率会虚高。"""
    records = [
        _record("c1", "V1", "A0", "m", "clinic", "呼吸内科"),
        _record("c1", "V2", "A0", "m", "clinic", "呼吸内科"),
        _record("c1", "V4", "A0", "m", None, None, status="clarification"),
    ]

    assert metrics.consistency(records, "triage") == 1.0
    row = metrics.summary(records)[0]
    assert row.clarification_rate == 1 / 3
    assert row.effective_units == 2


def test_red_flag_miss_rate_counts_only_units_that_should_have_hit() -> None:
    records = [
        _record("c1", "V1", "Aall", "m", "emergency", "急诊科", red_flags=["RF12"]),
        _record("c1", "V2", "Aall", "m", "clinic", "呼吸内科", red_flags=["RF12"]),
        _record("c2", "V1", "Aall", "m", "clinic", "呼吸内科"),
    ]

    assert metrics.summary(records)[0].redflag_miss_rate == 0.5


def test_citation_pass_rate_uses_proposed_not_kept() -> None:
    records = [
        _record(
            "c1", "V1", "Aall", "m", "clinic", "呼吸内科", kept_conditions=["甲"], deleted_count=1
        ),
        _record("c1", "V2", "Aall", "m", "clinic", "呼吸内科", kept_conditions=[]),
    ]

    assert metrics.summary(records)[0].citation_pass_rate == 0.5


def test_cluster_bootstrap_brackets_the_point_estimate() -> None:
    values = {"c1": 1.0, "c2": 0.8, "c3": 0.6, "c4": 0.4}

    low, high = metrics.cluster_bootstrap(values, rounds=2000)

    assert low <= sum(values.values()) / len(values) <= high
    assert low < high
