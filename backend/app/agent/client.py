"""AgentArts 运行时调用客户端（docs/api-agentarts.md 16.2）。

职责边界：只负责传输与终态判定——request_json 字符串包装、SSE 帧缓存拼接、
workflow_finished 成功终态核对、schema 与 request_id 关联、超时与平台错误
映射（4001–4003）。内部业务状态（needs_clarification、draft_ready、failed
等）由调用方解读；草稿结构不合规（4004）也在调用方判定，这里不猜。

平台事件里 model 正文一律不读、不记，Authorization 与健康原文不进日志。
"""

import asyncio
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

import httpx

from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.core.config import get_settings

_REQUEST_SCHEMAS = {
    "profile": "clear-complaint.profile-intake.request.v1",
    "followup": "clear-complaint.followup-supplement.request.v1",
    # io.6（RouteSafe）：原文进、理解出，request.v2 / workflow.v2（api-agentarts 16.3-v2）
    "triage": "clear-complaint.triage.request.v2",
    # Daily-Health-Companion：响应只有 workflow.v1，DSL 版本走回显的 workflow_version（16.8.1）
    "daily": "clear-complaint.daily-companion.request.v1",
}
_RESPONSE_SCHEMAS = {
    "profile": "clear-complaint.profile-intake.workflow.v1",
    "followup": "clear-complaint.followup-supplement.workflow.v1",
    "triage": "clear-complaint.triage.workflow.v2",
    "daily": "clear-complaint.daily-companion.workflow.v1",
}
# 16.2.4 的超时表；总生成上限 60 秒是业务层的事，客户端只管单次调用
_TIMEOUT_SECONDS = {"profile": 30.0, "followup": 8.0, "triage": 50.0, "daily": 60.0}


@dataclass(frozen=True)
class Workflow:
    name: str
    url: str
    api_key: str
    request_schema: str
    response_schema: str
    timeout_seconds: float


def _workflow(name: str) -> Workflow:
    settings = get_settings()
    urls = {
        "profile": settings.agentarts_profile_intake_url,
        "followup": settings.agentarts_followup_supplement_url,
        "triage": settings.agentarts_triage_url,
        "daily": settings.agentarts_daily_companion_url,
    }
    keys = {
        "profile": settings.agentarts_profile_intake_api_key,
        "followup": settings.agentarts_followup_supplement_api_key,
        "triage": settings.agentarts_triage_api_key,
        "daily": settings.agentarts_daily_companion_api_key,
    }
    if name not in urls:
        raise ValueError(f"未知工作流: {name}")
    return Workflow(
        name=name,
        url=urls[name],
        api_key=keys[name],
        request_schema=_REQUEST_SCHEMAS[name],
        response_schema=_RESPONSE_SCHEMAS[name],
        timeout_seconds=_TIMEOUT_SECONDS[name],
    )


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _parse_event(raw: str) -> dict[str, object] | None:
    try:
        payload: object = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _unavailable(message: str) -> BizException:
    return BizException(ErrorCode.AGENTARTS_UNAVAILABLE, message)


async def invoke_workflow(
    name: str,
    business_request: Mapping[str, object],
    platform_session_id: str,
    *,
    timeout_seconds: float | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, object]:
    """调用一条工作流，返回内部业务结果对象。

    business_request 是 16.3–16.5 的业务对象，本函数负责包成
    inputs.request_json 字符串；平台会话 ID 只用于 x-hw-agentarts 头，
    不替代任何业务归属校验。失败抛 BizException（4001/4002/4003）。
    """
    wf = _workflow(name)
    if not wf.url or not wf.api_key:
        raise _unavailable(f"{name} 运行时地址或凭据未配置")
    if business_request.get("schema_version") != wf.request_schema:
        # 这是调用方的程序错误，不是平台故障，不能折成 4xxx 混给用户
        raise ValueError("business_request 的 schema_version 与工作流不符")

    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-Invoke-Mode": get_settings().agentarts_invoke_mode,
        "x-hw-agentarts-session-id": platform_session_id,
        "X-Request-Id": str(uuid.uuid4()),
        "Authorization": f"Bearer {wf.api_key}",
    }
    payload = {
        "inputs": {
            "request_json": json.dumps(business_request, ensure_ascii=False, allow_nan=False)
        }
    }

    data_lines: list[str] = []
    terminal: dict[str, object] | None = None
    try:
        async with asyncio.timeout(
            wf.timeout_seconds if timeout_seconds is None else timeout_seconds
        ):
            # SSE 在模型生成期间可能长时间无字节，httpx 默认 5 秒读超时会误杀；
            # 总时长由外层 asyncio.timeout 管，这里只放宽单次读等待
            async with (
                httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(60.0)) as client,
                client.stream("POST", wf.url, headers=headers, json=payload) as response,
            ):
                if response.status_code != 200:
                    code = (
                        ErrorCode.AGENTARTS_THROTTLED
                        if response.status_code == 429
                        else ErrorCode.AGENTARTS_UNAVAILABLE
                    )
                    raise BizException(code, f"平台 HTTP {response.status_code}")
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())
                        continue
                    if line or not data_lines:
                        continue
                    event = _parse_event("\n".join(data_lines))
                    data_lines.clear()
                    if event is None:
                        raise _unavailable("平台事件不是合法 JSON")
                    kind = event.get("event")
                    if kind in {"error", "exception", "node_wait"}:
                        # 本版三条任务都不依赖平台暂停等待回复，终态前出现即失败
                        raise _unavailable(f"平台事件异常: {kind}")
                    if kind == "workflow_finished":
                        terminal = event
                        break
    except TimeoutError:
        raise BizException(ErrorCode.AGENTARTS_TIMEOUT) from None

    if terminal is None:
        raise _unavailable("响应流结束但未收到成功终态")

    event_data = _mapping(terminal.get("data"))
    status = _mapping(event_data.get("status"))
    if status.get("desc") != "succeeded":
        raise _unavailable("平台执行未成功完成")
    outputs = _mapping(event_data.get("outputs"))
    content = outputs.get("responseContent")
    if not isinstance(content, str) or not content.strip():
        raise _unavailable("平台最终业务正文为空")

    try:
        result: object = json.loads(content)
    except json.JSONDecodeError:
        raise _unavailable("平台最终业务正文不是合法 JSON") from None
    if not isinstance(result, dict):
        raise _unavailable("平台最终业务正文不是对象")
    payload_result = _mapping(result)
    if payload_result.get("schema_version") != wf.response_schema:
        raise _unavailable("工作流业务协议不匹配")
    if payload_result.get("request_id") != business_request.get("request_id"):
        raise _unavailable("工作流请求关联不匹配")
    return payload_result
