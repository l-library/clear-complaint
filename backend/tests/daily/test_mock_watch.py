"""合成手表数据：确定性、25 项键齐全、缺失用 null 而不是 0。"""

from datetime import date

from app.daily import mock_watch

# 16.8.3 表里的 25 项，测试按文档独立列一遍，防止代码里悄悄少一项
DOCUMENTED_KEYS = {
    "hr",
    "rhr",
    "hrv",
    "spo2",
    "blood_pressure",
    "ecg",
    "respiratory_rate",
    "skin_temperature",
    "sleep_duration",
    "deep_sleep",
    "light_sleep",
    "rem_sleep",
    "awakenings",
    "steps",
    "distance",
    "calories_burned",
    "exercise_duration",
    "activity_type",
    "activity_intensity",
    "vo2_max",
    "hrr",
    "stress_level",
    "fall_detection",
    "recovery_score",
    "menstrual_cycle",
}

DAY = date(2026, 11, 23)


def test_metric_key_table_matches_document() -> None:
    assert set(mock_watch.METRIC_KEYS) == DOCUMENTED_KEYS
    assert len(mock_watch.METRIC_KEYS) == 25


def test_same_user_same_day_is_byte_identical() -> None:
    first = mock_watch.build_watch_data(7, DAY)
    second = mock_watch.build_watch_data(7, DAY)

    assert first == second
    assert first["date"] == "2026-11-23"
    assert first["device"] == {
        "id": "MOCK-WATCH-007",
        "brand": "Synthetic",
        "model": "Demo",
    }


def test_other_day_or_user_differs() -> None:
    base = mock_watch.build_watch_data(7, DAY)

    assert mock_watch.build_watch_data(7, date(2026, 11, 24)) != base
    assert mock_watch.build_watch_data(8, DAY) != base


def test_every_metric_key_present_and_missing_is_null() -> None:
    watch = mock_watch.build_watch_data(7, DAY)
    metrics = watch["metrics"]

    assert isinstance(metrics, dict)
    assert set(metrics) == DOCUMENTED_KEYS
    # 核心五项每天都有值，其余按种子取子集，缺失的是 None 而不是 0
    for key in ("steps", "exercise_duration", "sleep_duration", "rhr", "activity_type"):
        assert metrics[key] is not None, key
    missing = [key for key, value in metrics.items() if value is None]
    assert missing, "合成数据应留出若干缺失项，才能覆盖「未提供」的展示分支"


def test_present_metrics_are_usable_and_never_zero() -> None:
    for day in (DAY, date(2026, 11, 24), date(2026, 12, 1)):
        metrics = mock_watch.build_watch_data(11, day)["metrics"]
        assert isinstance(metrics, dict)
        for key, value in metrics.items():
            if value is None:
                continue
            assert isinstance(value, dict), key
            assert value.get("quality") == "usable", key
            assert value.get("value") not in (None, 0, ""), key
            assert "unit" in value or key in ("activity_type",), key


def test_wear_minutes_within_contract_range() -> None:
    for day in (DAY, date(2026, 11, 24), date(2026, 12, 1)):
        wear = mock_watch.build_watch_data(11, day)["wear_minutes"]
        assert isinstance(wear, int)
        assert 0 < wear <= 1440
