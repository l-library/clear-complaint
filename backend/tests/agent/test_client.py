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

from app.agent.client import invoke_workflow
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


def _transport(frames: list[str], status: int = 200) -> httpx.MockTransport:
    body = "".join(f"data: {frame}\n\n" for frame in frames).encode()
    headers = {"content-type": "text/event-stream"}
    response = httpx.Response(status, headers=headers, content=body)

    async def handler(request: httpx.Request) -> httpx.Response:
        return response

    return httpx.MockTransport(handler)


@pytest.fixture
def profile_config(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "agentarts_profile_intake_url", "https://platform.test/profile")
    monkeypatch.setattr(settings, "agentarts_profile_intake_api_key", "test-key")


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
