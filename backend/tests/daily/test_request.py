"""请求组装与信任边界：九键白名单、必填与日期一致、条数与体积上限、本地安全标记。"""

from typing import Any

import pytest

from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.daily import archive as archive_module
from app.daily import service
from daily.support import DAY, watch_data_with

NINE_KEYS = {
    "schema_version",
    "request_id",
    "report_date",
    "timezone",
    "data_source",
    "watch_data",
    "health_archive",
    "baseline",
    "safety_context",
}


def _request(**overrides: object) -> dict[str, Any]:
    watch = watch_data_with(1)
    archive: dict[str, object] = {
        "snapshot_id": archive_module.payload_hash({}),
        "profile": {},
        "confirmed_conditions": [],
        "consultations": [],
        "medical_records": [],
        "care_guidance": [],
    }
    request = service.build_request(
        request_id="daily-1-2026-11-23-abcd1234",
        report_date=DAY,
        watch_data=watch,
        health_archive=archive,
        safety=service.safety_context(watch),
    )
    request.update(overrides)
    return request


def test_request_key_set_is_exactly_the_whitelisted_subset() -> None:
    request = _request()

    # baseline 需要同设备 7 天历史，v1 没有来源，按 16.8.5「没有就省略」不发送
    assert set(request) == NINE_KEYS - {"baseline"}
    assert set(request) <= NINE_KEYS
    assert request["schema_version"] == "clear-complaint.daily-companion.request.v1"
    assert request["timezone"] == "Asia/Shanghai"
    assert request["data_source"] == "mock"
    assert request["report_date"] == "2026-11-23"
    watch = request["watch_data"]
    assert isinstance(watch, dict) and watch["date"] == request["report_date"]


def test_request_rejects_extra_top_level_key() -> None:
    request = _request(user_memory={"note": "调试字段"})

    with pytest.raises(BizException) as excinfo:
        service.validate_request(request)

    assert excinfo.value.code is ErrorCode.INVALID_PARAM
    assert "user_memory" in excinfo.value.message


def test_request_rejects_watch_date_mismatch() -> None:
    request = _request()
    watch = dict(request["watch_data"])
    watch["date"] = "2026-11-22"
    request["watch_data"] = watch

    with pytest.raises(BizException) as excinfo:
        service.validate_request(request)

    assert excinfo.value.code is ErrorCode.INVALID_PARAM
    assert "watch_data.date" in excinfo.value.message


def test_request_rejects_missing_required_key() -> None:
    request = _request()
    del request["safety_context"]

    with pytest.raises(BizException) as excinfo:
        service.validate_request(request)

    assert "safety_context" in excinfo.value.message


@pytest.mark.parametrize(
    ("field", "rows", "limit"),
    [
        ("consultations", archive_module.CONSULTATION_LIMIT + 1, "consultations"),
        ("medical_records", archive_module.CONSULTATION_LIMIT + 1, "medical_records"),
        ("confirmed_conditions", service.CONDITION_LIMIT + 1, "confirmed_conditions"),
        ("care_guidance", service.GUIDANCE_LIMIT + 1, "care_guidance"),
    ],
)
def test_request_rejects_over_limit_rows(field: str, rows: int, limit: str) -> None:
    request = _request()
    built = dict(request["health_archive"])
    built[field] = [{"id": f"x{index}", "summary": "合成"} for index in range(rows)]
    request["health_archive"] = built

    with pytest.raises(BizException) as excinfo:
        service.validate_request(request)

    assert excinfo.value.code is ErrorCode.INVALID_PARAM
    assert limit in excinfo.value.message


def test_request_rejects_over_long_summary() -> None:
    request = _request()
    built = dict(request["health_archive"])
    built["consultations"] = [{"id": "ep1", "summary": "咳" * (archive_module.SUMMARY_CHARS + 1)}]
    request["health_archive"] = built

    with pytest.raises(BizException) as excinfo:
        service.validate_request(request)

    assert "summary" in excinfo.value.message


def test_request_rejects_oversized_json(monkeypatch: pytest.MonkeyPatch) -> None:
    # 条数与每条长度都有上限，v1 的薄档案堆不到 180000 字符；把线压低才能验证
    # 体积分支本身（超限报错，不静默截断）
    monkeypatch.setattr(service, "REQUEST_CHAR_LIMIT", 500)

    with pytest.raises(BizException) as excinfo:
        service.validate_request(_request())

    assert excinfo.value.code is ErrorCode.INVALID_PARAM
    assert "500" in excinfo.value.message


def test_safety_context_disallows_individual_plans_in_v1() -> None:
    context = service.safety_context(watch_data_with(1))

    assert context == {
        "review_required": False,
        "activity_allowed": False,
        "sleep_advice_allowed": False,
    }


def test_review_reasons_flags_usable_fall_and_ecg_labels() -> None:
    fall = watch_data_with(1, fall_detection={"detected": True, "quality": "usable"})
    assert service.review_reasons(fall) == ["fall_detection"]

    ecg = watch_data_with(
        1, ecg={"recorded": True, "device_label": "inconclusive", "quality": "usable"}
    )
    assert service.review_reasons(ecg) == ["ecg:inconclusive"]

    normal = watch_data_with(
        1,
        fall_detection={"detected": False, "quality": "usable"},
        ecg={"recorded": True, "device_label": "normal", "quality": "usable"},
    )
    assert service.review_reasons(normal) == []


def test_review_reasons_ignores_low_quality_and_missing_metrics() -> None:
    low_quality = watch_data_with(
        1,
        fall_detection={"detected": True, "quality": "low"},
        ecg={"recorded": True, "device_label": "abnormal", "quality": "low"},
    )
    assert service.review_reasons(low_quality) == []

    absent = watch_data_with(1, fall_detection=None, ecg=None)
    assert service.review_reasons(absent) == []


def test_safety_context_marks_review_required_from_metrics() -> None:
    watch = watch_data_with(
        1, ecg={"recorded": True, "device_label": "abnormal", "quality": "usable"}
    )

    assert service.safety_context(watch)["review_required"] is True
