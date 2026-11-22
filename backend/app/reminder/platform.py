"""Followup-Supplement 工作流的调用缝，测试在这里打桩。"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from app.agent.client import invoke_workflow


async def call_followup(
    business_request: Mapping[str, object], platform_session_id: str
) -> dict[str, object]:
    """与 triage 同理：每次调用新会话 ID，超时 8 秒且不重试（16.2.4）。"""
    return await invoke_workflow("followup", business_request, platform_session_id)


def fresh_session_id() -> str:
    return uuid4().hex
