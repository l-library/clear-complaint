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
# 平台侧 answers 最多 100 项（api-agentarts 16.3-v2 字段表）
ANSWER_LEDGER_LIMIT = 100
# 提问计数（契约第 5 节）：唯一问题计，unknown/skip 计入，重试不计数
ASK_LIMIT_INITIAL = 10
ASK_LIMIT_REVISION = 5


def validate_understanding(
    value: object, *, episode_id: int | None = None
) -> dict[str, Any] | None:
    """首次调用传 None；此后回传上次响应的 understanding 对象。

    只做信任边界校验：必须是对象、序列化后不超过体积上限；对象自带 episode_id
    时必须与当前问诊一致，防止跨问诊状态被注进请求。内容是工作流的内部状态，
    后端不读也不改，避免两边各自解释一遍。
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise BizException(ErrorCode.INVALID_PARAM, "understanding 须为对象")
    if len(json.dumps(value, ensure_ascii=False)) > UNDERSTANDING_MAX_CHARS:
        raise BizException(ErrorCode.INVALID_PARAM, "understanding 状态超出体积上限")
    marker = value.get("episode_id")
    if episode_id is not None and isinstance(marker, str) and marker != str(episode_id):
        raise BizException(ErrorCode.INVALID_PARAM, "understanding 归属与当前问诊不符")
    return value


def validate_answers(answers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """answers 是累计原文台账：answer_id/question_id/action/text 四项，逐条校验。

    主动补充允许 question_id=None；unknown 与 skip 的 text 允许空串，
    但不转写成「没有」，原文有什么传什么。
    """
    if len(answers) > ANSWER_LEDGER_LIMIT:
        raise BizException(ErrorCode.INVALID_PARAM, "answers 台账超出上限")
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


# 理解输出的 normalized 用平台字段名，公开展示字段名反向映射（symptom 特判为列表）
PLATFORM_TO_PUBLIC = {
    "symptom": "symptom",
    "onset": "onset_at",
    "duration": "duration_text",
    "location": "site",
    "character": "nature",
    "associated_symptoms": "associated",
    "medication": "medications_text",
}


# ---- 结果修订与提问台账（issue #23 契约第 1、3、5 节） ----
# 旧结果只保留最近三版：修订是低频对象，回看用，不建独立表
RESULT_HISTORY_CAP = 3


def append_answer(
    episode: Episode, question_id: str | None, action: str, text: str
) -> dict[str, Any]:
    """把一条回答原文记入台账，answer_id 按 episode 内序号生成、稳定可回查。

    台账只增不改：更正以新条目表达，工作流合并时自行取舍。
    """
    ledger: list[dict[str, Any]] = list(episode.raw_answers or [])
    entry: dict[str, Any] = {
        "answer_id": f"a{len(ledger) + 1}",
        "question_id": question_id,
        "action": action,
        "text": text,
    }
    ledger.append(entry)
    validate_answers(ledger)
    episode.raw_answers = ledger
    return entry


def new_question_id(episode: Episode) -> str:
    state = episode.clarify_state or {}
    questions = state.get("questions")
    return f"q{len(questions) + 1}" if isinstance(questions, dict) else "q1"


def register_question(
    episode: Episode, question_id: str, purpose: str, text: str, can_skip: bool
) -> bool:
    """记录一次下发的问题；重复收到同一 question_id 不重复计数（契约第 3 节）。

    计数按唯一问题，unknown/skip 计入，网络重试由这里的幂等性兜住。
    """
    if purpose not in QUESTION_PURPOSES:
        raise BizException(ErrorCode.INVALID_PARAM, "question.purpose 取值不合法")
    state: dict[str, Any] = dict(episode.clarify_state or {})
    raw_questions = state.get("questions")
    questions: dict[str, Any] = dict(raw_questions) if isinstance(raw_questions, dict) else {}
    if question_id in questions:
        return False
    questions[question_id] = {"purpose": purpose, "text": text, "can_skip": can_skip}
    state["questions"] = questions
    state["asked_count"] = int(state.get("asked_count") or 0) + 1
    episode.clarify_state = state
    return True


def asked_count(episode: Episode) -> int:
    state = episode.clarify_state or {}
    raw = state.get("asked_count")
    return int(raw) if isinstance(raw, int) and not isinstance(raw, bool) else 0


def ask_limit_for(episode: Episode) -> int:
    """当前所处周期的问题上限：初始 10，结果后补充每修订周期 5（契约第 5 节）。"""
    return ASK_LIMIT_INITIAL if episode.result is None else ASK_LIMIT_REVISION


def supersede_result(episode: Episode, new_result: dict[str, Any], new_gate: dict[str, Any]) -> int:
    """接受一版新结果：旧版本进回看历史（cap 3），修订号推进。

    编号口径与平台对齐（api-agentarts 16.3-v2，实测确认）：首版结果即
    revision=1，base_revision=0 表示尚无结果——补充请求若带 0 会被平台按
    「无结果基线」拒绝。归档时间与提醒不随修订重置（#28 语义），由调用方
    保证，这里只管结果版本。
    """
    if episode.result is not None:
        history: list[dict[str, Any]] = list(episode.result_history or [])
        history.append(
            {
                "revision": int(episode.revision or 0),
                "result": episode.result,
                "gate": episode.gate,
                "saved_at": format_shanghai(episode.saved_at) if episode.saved_at else None,
            }
        )
        episode.result_history = history[-RESULT_HISTORY_CAP:]
    episode.revision = int(episode.revision or 0) + 1
    episode.result = new_result
    episode.gate = new_gate
    return int(episode.revision or 0)


def is_stale_revision(episode: Episode, base_revision: int) -> bool:
    """迟到结果判定：工作流回显的 base_revision 低于当前修订号即拒收（契约第 1 节）。"""
    return int(base_revision) < int(episode.revision or 0)


def store_understanding(
    episode: Episode, blob: dict[str, Any] | None, *, episode_id: int | None = None
) -> None:
    """落库工作流回传的 understanding：校验（含归属）后原样保存，下一轮原样回传。"""
    episode.understanding = validate_understanding(blob, episode_id=episode_id)
