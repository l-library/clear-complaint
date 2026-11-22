"""平台调用的薄适配层：隔离可替换点，测试在这里打桩。"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from app.agent.client import invoke_workflow


async def call_triage(
    business_request: Mapping[str, object], platform_session_id: str
) -> dict[str, object]:
    """每次调用用新会话 ID：实测复用同一会话跨不同问诊会得到 INVALID_REQUEST。"""
    return await invoke_workflow("triage", business_request, platform_session_id)


def fresh_session_id() -> str:
    return uuid4().hex
