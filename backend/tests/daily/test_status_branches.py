"""五种 status 分支：四种报告状态落库、invalid_input 报错不落库、本地待核实短路不调平台。"""

from datetime import date
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.daily import mock_watch, service
from daily.support import (
    DAY,
    WORKFLOW_VERSION,
    RunDb,
    add_episode,
    generate,
    invalid_input_result,
    platform_result,
    stored,
    stub_platform,
    watch_data_with,
)

# 与 docs/api-agentarts.md 16.8.7 样例同字段名，只留测试要断言的部分
SUMMARY = {
    "title": "今天的健康小结",
    "greeting": "今天辛苦了。",
    "highlights": [{"id": "metric:steps", "label": "步数", "text": "今天记录了 4600 步。"}],
    "health_connections": [],
    "gentle_reminders": [],
    "tomorrow_actions": [],
    "closing": "照顾好自己。",
    "limitations": "单日设备记录不能判断疾病变化。",
}


def test_ready_status_is_persisted_with_version_echo(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(
        monkeypatch,
        lambda request: platform_result(request, status="ready", summary=SUMMARY),
    )

    row = generate(run_db, user_id)

    assert row["status"] == "ready"
    assert row["summary"] == SUMMARY
    assert row["data_source"] == "mock"
    # 版本存平台回显值，客户端不写死断言
    assert row["workflow_version"] == WORKFLOW_VERSION
    assert row["report_date"] == DAY
    assert row["used_record_ids"] == []
    assert len(row["input_snapshot_hash"]) == 64


def test_degraded_status_keeps_template_copy(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(
        monkeypatch,
        lambda request: platform_result(request, status="degraded", summary=SUMMARY),
    )

    row = generate(run_db, user_id)

    # degraded 允许降级展示，前端靠内部 status 打标记，正文仍是可追溯的模板兜底
    assert row["status"] == "degraded"
    assert row["summary"] == SUMMARY
    assert row["workflow_version"] == WORKFLOW_VERSION


def test_data_insufficient_status_is_persisted(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(
        monkeypatch,
        lambda request: platform_result(
            request,
            status="data_insufficient",
            summary=SUMMARY | {"highlights": []},
            data_quality={"available_metric_ids": [], "coverage_limited": False},
        ),
    )

    row = generate(run_db, user_id)

    assert row["status"] == "data_insufficient"
    quality = row["data_quality"]
    assert isinstance(quality, dict)
    # 判空用 available_metric_ids，不能拿 coverage_limited 当空指标信号
    assert quality["available_metric_ids"] == []
    assert quality["coverage_limited"] is False


def test_review_required_from_platform_is_persisted(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(monkeypatch, lambda request: platform_result(request, status="review_required"))

    row = generate(run_db, user_id)

    assert row["status"] == "review_required"
    assert row["workflow_version"] == WORKFLOW_VERSION


def test_local_fall_detection_short_circuits_platform(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    watch = watch_data_with(user_id, fall_detection={"detected": True, "quality": "usable"})
    monkeypatch.setattr(mock_watch, "build_watch_data", lambda *_: watch)

    def boom(_: object) -> dict[str, Any]:
        raise AssertionError("本地已判定 review_required，不应调用平台")

    stub_platform(monkeypatch, boom)

    row = generate(run_db, user_id)

    assert row["status"] == "review_required"
    # 未调用平台就没有回显版本；空串表示后端本地判定
    assert row["workflow_version"] == ""
    assert row["summary"] is None
    assert row["data_source"] == "mock"


def test_local_ecg_label_short_circuits_platform(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    watch = watch_data_with(
        user_id, ecg={"recorded": True, "device_label": "abnormal", "quality": "usable"}
    )
    monkeypatch.setattr(mock_watch, "build_watch_data", lambda *_: watch)

    def boom(_: object) -> dict[str, Any]:
        raise AssertionError("ECG 待核实标签不应走到平台调用")

    stub_platform(monkeypatch, boom)

    row = generate(run_db, user_id)

    assert row["status"] == "review_required"
    assert row["workflow_version"] == ""


def test_local_review_takes_precedence_over_earlier_ready_row(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(monkeypatch, lambda request: platform_result(request, summary=SUMMARY))
    first = generate(run_db, user_id)
    assert first["status"] == "ready"

    watch = watch_data_with(user_id, fall_detection={"detected": True, "quality": "usable"})
    monkeypatch.setattr(mock_watch, "build_watch_data", lambda *_: watch)
    rows = stored(run_db, user_id)
    assert len(rows) == 1

    later = generate(run_db, user_id)

    # 平台升版或本地判定用不同 workflow_version 各留一行，读侧取最新的一份
    rows = stored(run_db, user_id)
    assert len(rows) == 2
    assert rows[-1]["id"] == later["id"]
    assert rows[-1]["status"] == "review_required"
    assert rows[-1]["updated_at"] > rows[0]["updated_at"]


def test_invalid_input_raises_and_saves_nothing(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(monkeypatch, invalid_input_result)

    # 失败空壳（summary=null、data_quality={}、data_source=unknown、report_date=""）
    # 不能盖住真实错误原因，报错而不是解析异常
    with pytest.raises(BizException) as excinfo:
        generate(run_db, user_id)

    assert excinfo.value.code is ErrorCode.INVALID_PARAM
    assert stored(run_db, user_id) == []


def test_unknown_status_is_a_platform_failure(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(monkeypatch, lambda request: platform_result(request, status="weird"))

    with pytest.raises(BizException) as excinfo:
        generate(run_db, user_id)

    assert excinfo.value.code is ErrorCode.AGENTARTS_UNAVAILABLE
    assert stored(run_db, user_id) == []


@pytest.mark.parametrize(
    "echo",
    [
        {"report_date": "2026-11-22"},
        {"data_source": "device"},
        {"health_archive_snapshot_id": "other-snapshot"},
    ],
)
def test_echo_mismatch_does_not_save(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch, echo: dict[str, object]
) -> None:
    stub_platform(monkeypatch, lambda request: platform_result(request, summary=SUMMARY, echo=echo))

    with pytest.raises(BizException) as excinfo:
        generate(run_db, user_id)

    assert excinfo.value.code is ErrorCode.AGENTARTS_UNAVAILABLE
    assert stored(run_db, user_id) == []


def test_used_record_ids_are_verified_against_the_archive(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    episode_id = add_episode(run_db, user_id)
    stub_platform(
        monkeypatch,
        lambda request: platform_result(
            request, used_record_ids=[f"ep{episode_id}", "MEDICAL-404"]
        ),
    )

    row = generate(run_db, user_id)

    # 能回查到来源的保留，编造的来源丢弃（记录日志），不落进可展示的来源列表
    assert row["used_record_ids"] == [f"ep{episode_id}"]


def test_platform_failure_propagates_without_saving(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(business_request: object, platform_session_id: str) -> dict[str, object]:
        raise BizException(ErrorCode.AGENTARTS_TIMEOUT)

    monkeypatch.setattr("app.daily.platform.call_daily", boom)

    with pytest.raises(BizException) as excinfo:
        generate(run_db, user_id)

    assert excinfo.value.code is ErrorCode.AGENTARTS_TIMEOUT
    assert stored(run_db, user_id) == []


def test_generate_uses_today_when_date_is_omitted(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.common.clock import now_shanghai

    stub_platform(monkeypatch, lambda request: platform_result(request))

    async def op(session: AsyncSession) -> dict[str, Any]:
        row = await service.generate_daily_report(session, user_id=user_id)
        return {"report_date": row.report_date}

    result = run_db(op)

    assert result["report_date"] == now_shanghai().date()
    assert isinstance(result["report_date"], date)
