"""Daily-Health-Companion 工作流的调用缝，测试在这里打桩（同 episode/platform.py）。"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from app.agent.client import invoke_workflow


async def call_daily(
    business_request: Mapping[str, object], platform_session_id: str
) -> dict[str, object]:
    """超时 60 秒由客户端超时表给定（16.8.1 的工程总预算），业务层不重试。"""
    return await invoke_workflow("daily", business_request, platform_session_id)


def fresh_session_id() -> str:
    return uuid4().hex
