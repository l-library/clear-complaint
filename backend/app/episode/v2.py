"""triage `request.v2` 的组装与边界校验（issue #23 契约确认稿）。

v2 把理解交给工作流的理解节点：请求只带主诉原文、累计回答原文、上次返回的
understanding 状态、近 90 天问诊摘要与当前用药（#25）。后端不再做字段级
预处理，normalize() 的字符折算只保留给红旗规则。

本模块是纯组装层，v1→v2 的管线切换由后续状态机改动一次性完成；切换前 v1
路径保持在线，这里不改动任何现有调用方。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.archive import service as archive_service
from app.common.clock import format_shanghai
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.episode import compose
from app.episode.models import STATUS_SAVED, Episode

SCHEMA_VERSION = "clear-complaint.triage.request.v2"
RESPONSE_SCHEMA_VERSION = "clear-complaint.triage.workflow.v2"

# 答案动作三值：unknown 与 skip 都不转成「没有」（契约第 1 节）
ANSWER_ACTIONS = ("answer", "unknown", "skip")
# 单问 purpose 的受控枚举；other 留给歧义确认与主动补充类提问（契约第 3 节）
QUESTION_PURPOSES = (
    "onset",
    "duration",
    "location",
    "character",
    "associated_symptoms",
    "medication",
    "other",
)

# #25 的 history_context 上限，与 Daily 16.8.4 同构
HISTORY_DAYS = 90
CONSULTATION_LIMIT = 60
SUMMARY_CHARS = 800
MEDICATION_LIMIT = 40
# understanding 是工作流回传的不透明状态：后端只管体积与结构，不解释内容
UNDERSTANDING_MAX_CHARS = 65536
ANSWER_TEXT_MAX_CHARS = 500
# 提问计数（契约第 5 节）：唯一问题计，unknown/skip 计入，重试不计数
ASK_LIMIT_INITIAL = 10
ASK_LIMIT_REVISION = 5


def validate_understanding(value: object) -> dict[str, Any] | None:
    """首次调用传 None；此后回传上次响应的 understanding 对象。

    只做信任边界校验：必须是对象、序列化后不超过体积上限。内容是工作流的
    内部状态，后端不读也不改，避免两边各自解释一遍。
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise BizException(ErrorCode.INVALID_PARAM, "understanding 须为对象")
    if len(json.dumps(value, ensure_ascii=False)) > UNDERSTANDING_MAX_CHARS:
        raise BizException(ErrorCode.INVALID_PARAM, "understanding 状态超出体积上限")
    return value


def validate_answers(answers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """answers 是累计原文台账：answer_id/question_id/action/text 四项，逐条校验。

    主动补充允许 question_id=None；unknown 与 skip 的 text 允许空串，
    但不转写成「没有」，原文有什么传什么。
    """
    seen: set[str] = set()
    for answer in answers:
        answer_id = str(answer.get("answer_id", ""))
        if not answer_id or answer_id in seen:
            raise BizException(ErrorCode.INVALID_PARAM, "answer_id 缺失或重复")
        seen.add(answer_id)
        action = str(answer.get("action", ""))
        if action not in ANSWER_ACTIONS:
            raise BizException(ErrorCode.INVALID_PARAM, "answer.action 取值不合法")
        text = answer.get("text", "")
        if not isinstance(text, str) or len(text) > ANSWER_TEXT_MAX_CHARS:
            raise BizException(
                ErrorCode.INVALID_PARAM, f"answer.text 须为不超过 {ANSWER_TEXT_MAX_CHARS} 字的原文"
            )
        question_id = answer.get("question_id")
        if question_id is not None and not isinstance(question_id, str):
            raise BizException(ErrorCode.INVALID_PARAM, "question_id 须为字符串或 null")
    return answers


def _consultation_summary(episode: Episode) -> str:
    result = episode.result or {}
    label = compose.TRIAGE_LABELS.get(str(result.get("triage", "")), "")
    department = str(result.get("department_primary", "") or "")
    summary = f"主诉：{episode.complaint_text}"
    if label:
        summary += f"；分诊：{label}"
    if department:
        summary += f"；建议科室：{department}"
    return summary[:SUMMARY_CHARS]


async def build_history_context(
    session: AsyncSession,
    user_id: int,
    now: datetime,
    *,
    exclude_episode_id: int | None = None,
) -> dict[str, Any]:
    """#25：近 90 天已归档问诊摘要 + 当前用药，交给理解节点做上下文。

    摘要与用药的上限、每条长度都按契约固定；摘要内容由后端组装，工作流不
    自行查库。当前问诊自身不在自己的上下文里。
    """
    since = now - timedelta(days=HISTORY_DAYS)
    query = (
        select(Episode)
        .where(
            Episode.user_id == user_id,
            Episode.status == STATUS_SAVED,
            Episode.created_at >= since,
        )
        .order_by(Episode.created_at.desc())
        .limit(CONSULTATION_LIMIT)
    )
    if exclude_episode_id is not None:
        query = query.where(Episode.id != exclude_episode_id)
    rows = (await session.execute(query)).scalars().all()
    consultations = [
        {
            "id": f"ep{row.id}",
            "occurred_on": format_shanghai(row.created_at)[:10],
            "summary": _consultation_summary(row),
        }
        for row in rows
    ]
    medications = await archive_service.active_medications_brief(session, user_id, MEDICATION_LIMIT)
    return {"consultations": consultations, "medications": medications}


def build_v2_request(
    *,
    episode_id: int,
    request_id: str,
    complaint_text: str,
    answers: list[dict[str, Any]],
    understanding: dict[str, Any] | None,
    history_context: dict[str, Any],
    profile_snapshot: dict[str, Any],
    red_flag_ids: list[str],
    asked_count: int,
    ask_limit: int,
    skipped: bool,
    base_revision: int,
) -> dict[str, Any]:
    """组装 request.v2。删除项：normalized 七字段、self_attribution、
    vitals_snapshot、env——理解与归因归理解节点，后端不再预提取。
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "episode_id": str(episode_id),
        "episode_status": "generating",
        "complaint_text": complaint_text,
        "answers": validate_answers(answers),
        "understanding": validate_understanding(understanding),
        "history_context": history_context,
        "profile_snapshot": profile_snapshot,
        "red_flags": {"checked": True, "version": 1, "matched_rule_ids": red_flag_ids},
        "clarification": {
            "asked_count": asked_count,
            "limit": ask_limit,
            "skipped": skipped,
        },
        "base_revision": base_revision,
    }
