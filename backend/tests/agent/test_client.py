"""AgentArts 客户端测试：SSE 终态判定、协议核对与平台错误映射。

全部用 MockTransport 合成事件流；真实平台调用是人工联调，不进 CI
（平台凭据与额度都不允许）。
"""

import asyncio
import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient  # noqa: F401  仅确保应用可导入

from app.agent.client import _workflow, invoke_workflow
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.core.config import get_settings

PROFILE_REQUEST: dict[str, Any] = {
    "schema_version": "clear-complaint.profile-intake.request.v1",
    "session_id": "SYNTHETIC-PROFILE-001",
    "request_id": "SYNTHETIC-INTAKE-001",
    "action": "start",
    "as_of_date": "2026-11-21",
    "form_snapshot": {},
    "medication_drafts": None,
    "active_field": None,
    "user_input": "",
    "skipped_fields": [],
    "unknown_fields": [],
    "required_fields": ["birth_date", "sex"],
}


def _response_payload(fields: dict[str, Any]) -> str:
    merged = {
        "schema_version": "clear-complaint.profile-intake.workflow.v1",
        "session_id": "SYNTHETIC-PROFILE-001",
        "request_id": "SYNTHETIC-INTAKE-001",
        "status": "needs_answer",
    }
    merged.update(fields)
    return json.dumps(merged, ensure_ascii=False)


DAILY_URL = "https://platform.test/daily"

DAILY_REQUEST: dict[str, Any] = {
    "schema_version": "clear-complaint.daily-companion.request.v1",
    "request_id": "SYNTHETIC-DAILY-001",
    "report_date": "2026-11-23",
    "timezone": "Asia/Shanghai",
    "data_source": "mock",
    "watch_data": {
        "date": "2026-11-23",
        "wear_minutes": 1380,
        "device": {"id": "MOCK-WATCH-001", "brand": "Synthetic", "model": "Demo"},
        "metrics": {
            "steps": {"value": 4600, "unit": "count", "quality": "usable"},
            "sleep_duration": {"value": 435, "unit": "min", "quality": "usable"},
        },
    },
    "health_archive": {
        "snapshot_id": "SYNTHETIC-ARCHIVE-001",
        "profile": {"preferred_name": "演示用户", "age": 68, "sex": "female"},
        "care_guidance": [
            {
                "id": "GUIDANCE-001",
                "record_id": "MEDICAL-001",
                "condition_id": "CONDITION-001",
                "topic": "activity",
                "confirmed": True,
                "text": "按此前确认的个人安排，在身体舒适的前提下分段步行。",
                "target": {"metric": "steps", "min": 3000, "max": 6000},
            }
        ],
    },
    "safety_context": {
        "review_required": False,
        "activity_allowed": True,
        "sleep_advice_allowed": True,
    },
}


def _daily_payload(fields: dict[str, Any]) -> str:
    merged: dict[str, Any] = {
        "schema_version": "clear-complaint.daily-companion.workflow.v1",
        "workflow_version": "2026-11-24.daily-companion.2",
        "request_id": "SYNTHETIC-DAILY-001",
        "report_date": "2026-11-23",
        "data_source": "mock",
        "status": "ready",
        "summary": {"title": "今天的健康小结"},
        "data_quality": {"available_metric_ids": ["steps", "sleep_duration"]},
        "used_record_ids": ["MEDICAL-001"],
    }
    merged.update(fields)
    return json.dumps(merged, ensure_ascii=False)


def _finished_frame(response_payload: str) -> str:
    return json.dumps(
        {
            "event": "workflow_finished",
            "data": {
                "status": {"code": 1, "desc": "succeeded"},
                "outputs": {"responseContent": response_payload},
            },
            "execution_id": "SYNTHETIC-EXECUTION-001",
        },
        ensure_ascii=False,
    )


def _transport(
    frames: list[str], status: int = 200, calls: list[httpx.Request] | None = None
) -> httpx.MockTransport:
    body = "".join(f"data: {frame}\n\n" for frame in frames).encode()
    headers = {"content-type": "text/event-stream"}
    response = httpx.Response(status, headers=headers, content=body)

    async def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return response

    return httpx.MockTransport(handler)


@pytest.fixture
def profile_config(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "agentarts_profile_intake_url", "https://platform.test/profile")
    monkeypatch.setattr(settings, "agentarts_profile_intake_api_key", "test-key")


@pytest.fixture
def daily_config(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "agentarts_daily_companion_url", DAILY_URL)
    monkeypatch.setattr(settings, "agentarts_daily_companion_api_key", "daily-test-key")


def test_happy_path_returns_internal_result(profile_config: None) -> None:
    frames = [
        json.dumps({"event": "workflow_started"}),
        json.dumps({"event": "message", "data": {"content": "模型正文，忽略"}}),
        _finished_frame(_response_payload({"next_question": {"field": "birth_date"}})),
        json.dumps({"event": "end"}),
    ]

    async def run() -> dict[str, object]:
        return await invoke_workflow(
            "profile", PROFILE_REQUEST, "SYNTHETIC-SESSION-001", transport=_transport(frames)
        )

    result = asyncio.run(run())

    assert result["status"] == "needs_answer"
    assert result["request_id"] == "SYNTHETIC-INTAKE-001"
    assert result["schema_version"] == "clear-complaint.profile-intake.workflow.v1"


def test_http_429_maps_to_throttled(profile_config: None) -> None:
    async def run() -> None:
        await invoke_workflow(
            "profile",
            PROFILE_REQUEST,
            "SYNTHETIC-SESSION-002",
            transport=_transport([], status=429),
        )

    with pytest.raises(BizException) as excinfo:
        asyncio.run(run())
    assert excinfo.value.code == ErrorCode.AGENTARTS_THROTTLED


def test_http_500_maps_to_unavailable(profile_config: None) -> None:
    async def run() -> None:
        await invoke_workflow(
            "profile",
            PROFILE_REQUEST,
            "SYNTHETIC-SESSION-003",
            transport=_transport([], status=500),
        )

    with pytest.raises(BizException) as excinfo:
        asyncio.run(run())
    assert excinfo.value.code == ErrorCode.AGENTARTS_UNAVAILABLE


def test_error_event_maps_to_unavailable(profile_config: None) -> None:
    frames = [
        json.dumps({"event": "workflow_started"}),
        json.dumps({"event": "error", "data": {"message": "boom"}}),
    ]

    async def run() -> None:
        await invoke_workflow(
            "profile", PROFILE_REQUEST, "SYNTHETIC-SESSION-004", transport=_transport(frames)
        )

    with pytest.raises(BizException) as excinfo:
        asyncio.run(run())
    assert excinfo.value.code == ErrorCode.AGENTARTS_UNAVAILABLE


def test_stream_without_terminal_maps_to_unavailable(profile_config: None) -> None:
    frames = [json.dumps({"event": "message", "data": {"content": "只有正文没有终态"}})]

    async def run() -> None:
        await invoke_workflow(
            "profile", PROFILE_REQUEST, "SYNTHETIC-SESSION-005", transport=_transport(frames)
        )

    with pytest.raises(BizException) as excinfo:
        asyncio.run(run())
    assert excinfo.value.code == ErrorCode.AGENTARTS_UNAVAILABLE


def test_failed_terminal_maps_to_unavailable(profile_config: None) -> None:
    frame = json.dumps(
        {"event": "workflow_finished", "data": {"status": {"code": 2, "desc": "failed"}}}
    )

    async def run() -> None:
        await invoke_workflow(
            "profile", PROFILE_REQUEST, "SYNTHETIC-SESSION-006", transport=_transport([frame])
        )

    with pytest.raises(BizException) as excinfo:
        asyncio.run(run())
    assert excinfo.value.code == ErrorCode.AGENTARTS_UNAVAILABLE


def test_schema_mismatch_maps_to_unavailable(profile_config: None) -> None:
    frames = [_finished_frame(_response_payload({"schema_version": "clear-complaint.other.v9"}))]

    async def run() -> None:
        await invoke_workflow(
            "profile", PROFILE_REQUEST, "SYNTHETIC-SESSION-007", transport=_transport(frames)
        )

    with pytest.raises(BizException) as excinfo:
        asyncio.run(run())
    assert excinfo.value.code == ErrorCode.AGENTARTS_UNAVAILABLE


def test_request_id_mismatch_maps_to_unavailable(profile_config: None) -> None:
    frames = [_finished_frame(_response_payload({"request_id": "NOT-MINE"}))]

    async def run() -> None:
        await invoke_workflow(
            "profile", PROFILE_REQUEST, "SYNTHETIC-SESSION-008", transport=_transport(frames)
        )

    with pytest.raises(BizException) as excinfo:
        asyncio.run(run())
    assert excinfo.value.code == ErrorCode.AGENTARTS_UNAVAILABLE


def test_timeout_maps_to_agentarts_timeout(profile_config: None) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.5)
        return httpx.Response(200)

    async def run() -> None:
        await invoke_workflow(
            "profile",
            PROFILE_REQUEST,
            "SYNTHETIC-SESSION-009",
            timeout_seconds=0.05,
            transport=httpx.MockTransport(handler),
        )

    with pytest.raises(BizException) as excinfo:
        asyncio.run(run())
    assert excinfo.value.code == ErrorCode.AGENTARTS_TIMEOUT


def test_unconfigured_runtime_maps_to_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "agentarts_profile_intake_url", "")
    monkeypatch.setattr(settings, "agentarts_profile_intake_api_key", "test-key")

    async def run() -> None:
        await invoke_workflow("profile", PROFILE_REQUEST, "SYNTHETIC-SESSION-010")

    with pytest.raises(BizException) as excinfo:
        asyncio.run(run())
    assert excinfo.value.code == ErrorCode.AGENTARTS_UNAVAILABLE


def test_wrong_request_schema_is_programmer_error(profile_config: None) -> None:
    broken = dict(PROFILE_REQUEST)
    broken["schema_version"] = "clear-complaint.triage.request.v1"

    async def run() -> None:
        await invoke_workflow("profile", broken, "SYNTHETIC-SESSION-011", transport=_transport([]))

    with pytest.raises(ValueError):
        asyncio.run(run())


def test_daily_mapping_uses_daily_settings(daily_config: None) -> None:
    wf = _workflow("daily")

    assert wf.url == DAILY_URL
    assert wf.api_key == "daily-test-key"
    assert wf.request_schema == "clear-complaint.daily-companion.request.v1"
    assert wf.response_schema == "clear-complaint.daily-companion.workflow.v1"
    assert wf.timeout_seconds == 60.0


def test_daily_request_is_wrapped_as_request_json_string(daily_config: None) -> None:
    calls: list[httpx.Request] = []

    async def run() -> None:
        await invoke_workflow(
            "daily",
            DAILY_REQUEST,
            "SYNTHETIC-SESSION-101",
            transport=_transport([_finished_frame(_daily_payload({}))], calls=calls),
        )

    asyncio.run(run())

    assert len(calls) == 1
    request = calls[0]
    assert str(request.url) == DAILY_URL
    assert request.headers["authorization"] == "Bearer daily-test-key"
    assert request.headers["x-hw-agentarts-session-id"] == "SYNTHETIC-SESSION-101"
    body = json.loads(request.content)
    assert list(body) == ["inputs"]
    assert isinstance(body["inputs"]["request_json"], str)
    assert json.loads(body["inputs"]["request_json"]) == DAILY_REQUEST


def test_daily_happy_path_returns_parsed_business_object(daily_config: None) -> None:
    frames = [
        json.dumps({"event": "workflow_started"}),
        _finished_frame(_daily_payload({"used_record_ids": []})),
    ]

    async def run() -> dict[str, object]:
        return await invoke_workflow(
            "daily", DAILY_REQUEST, "SYNTHETIC-SESSION-102", transport=_transport(frames)
        )

    result = asyncio.run(run())

    assert result["status"] == "ready"
    assert result["report_date"] == "2026-11-23"
    assert result["data_source"] == "mock"
    assert result["workflow_version"] == "2026-11-24.daily-companion.2"
    assert result["used_record_ids"] == []
    assert result["summary"] == {"title": "今天的健康小结"}


def test_daily_response_schema_mismatch_maps_to_unavailable(daily_config: None) -> None:
    # workflow.v2 不存在：DSL 版本走回显的 workflow_version，不拼进响应 schema
    frames = [
        _finished_frame(
            _daily_payload({"schema_version": "clear-complaint.daily-companion.workflow.v2"})
        )
    ]

    async def run() -> None:
        await invoke_workflow(
            "daily", DAILY_REQUEST, "SYNTHETIC-SESSION-103", transport=_transport(frames)
        )

    with pytest.raises(BizException) as excinfo:
        asyncio.run(run())
    assert excinfo.value.code == ErrorCode.AGENTARTS_UNAVAILABLE
    assert excinfo.value.message == "工作流业务协议不匹配"


def test_daily_unconfigured_runtime_maps_to_unavailable_without_http_call(
    monkeypatch: pytest.MonkeyPatch, daily_config: None
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "agentarts_daily_companion_api_key", "")
    calls: list[httpx.Request] = []

    async def run() -> None:
        await invoke_workflow(
            "daily",
            DAILY_REQUEST,
            "SYNTHETIC-SESSION-104",
            transport=_transport([_finished_frame(_daily_payload({}))], calls=calls),
        )

    with pytest.raises(BizException) as excinfo:
        asyncio.run(run())
    assert excinfo.value.code == ErrorCode.AGENTARTS_UNAVAILABLE
    assert calls == []


def test_daily_invalid_input_response_is_returned_intact(daily_config: None) -> None:
    # 16.8.7 末的空壳：summary null、data_quality {}、report_date ""、data_source unknown
    frames = [
        _finished_frame(
            _daily_payload(
                {
                    "status": "invalid_input",
                    "report_date": "",
                    "data_source": "unknown",
                    "summary": None,
                    "data_quality": {},
                    "used_record_ids": [],
                    "error_code": "INVALID_REQUEST",
                    "model_selection_applied": False,
                }
            )
        )
    ]

    async def run() -> dict[str, object]:
        return await invoke_workflow(
            "daily", DAILY_REQUEST, "SYNTHETIC-SESSION-105", transport=_transport(frames)
        )

    result = asyncio.run(run())

    assert result["status"] == "invalid_input"
    assert result["error_code"] == "INVALID_REQUEST"
    assert result["summary"] is None
    assert result["data_quality"] == {}
    assert result["report_date"] == ""
    assert result["data_source"] == "unknown"
    assert result["request_id"] == "SYNTHETIC-DAILY-001"
