"""问诊业务：创建、追问、生成、保存与事件流。

顺序照 docs/api.md 5.1：落记录 → 归一化 → 红旗判定 → 快照 → 澄清或生成。
红旗命中即短路急诊，不调模型；平台类错误（4001–4004）走兜底模板，
流仍以 done（degraded=true）结束；流式生成器内部消化异常，永不静默断流。
"""

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.account.models import Profile
from app.agent import redflag
from app.agent.citation import Condition as CitationCondition
from app.agent.citation import verify as verify_citations
from app.agent.normalize import split_attribution
from app.agent.vocab import known_terms
from app.agent.vocab import resolve as vocab_resolve
from app.common.clock import format_shanghai, now_shanghai
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.db.session import get_session
from app.episode import clarification, compose, platform
from app.episode.models import (
    STATUS_CLARIFYING,
    STATUS_FAILED,
    STATUS_GENERATING,
    STATUS_READY,
    STATUS_SAVED,
    Episode,
    EpisodeAnswer,
    IdempotencyKey,
)
from app.reminder import models as reminder_models
from app.reminder.service import create_episode_reminder

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 15
REPLAY_WAIT_SECONDS = 60
IDEMPOTENCY_WINDOW = timedelta(minutes=30)
# 平台类错误：流内放行兜底结果而不是 error 事件（docs/api.md 12 节）
PLATFORM_ERROR_CODES = {
    int(ErrorCode.AGENTARTS_UNAVAILABLE),
    int(ErrorCode.AGENTARTS_TIMEOUT),
    int(ErrorCode.AGENTARTS_THROTTLED),
    int(ErrorCode.AGENTARTS_DRAFT_INVALID),
}

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def parse_idempotency_key(raw: str | None) -> str:
    """Idempotency-Key：UUID v4、长度 36（docs/api.md 1.6）。"""
    if raw is None:
        raise BizException(ErrorCode.INVALID_PARAM, "缺少 Idempotency-Key 请求头")
    try:
        key = UUID(raw)
    except ValueError:
        raise BizException(ErrorCode.INVALID_PARAM, "Idempotency-Key 须为 UUID v4") from None
    if key.version != 4:
        raise BizException(ErrorCode.INVALID_PARAM, "Idempotency-Key 须为 UUID v4")
    return str(key)


def _fingerprint(body: dict[str, object]) -> str:
    payload = json.dumps(body, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


async def _load_owned(session: AsyncSession, user_id: int, episode_id: int) -> Episode:
    """2004 不区分"不存在 / 已过期 / 不是本人的"：不泄露存在性。"""
    episode = await session.get(Episode, episode_id)
    if episode is None or episode.user_id != user_id:
        raise BizException(ErrorCode.EPISODE_NOT_FOUND)
    if episode.expires_at < now_shanghai():
        raise BizException(ErrorCode.EPISODE_NOT_FOUND)
    return episode


# ---- 幂等 ----


async def _resolve_idempotency(
    session: AsyncSession, user_id: int, key: str, fingerprint: str
) -> Episode | None:
    """同键同体在窗口内 → 已有问诊（重放）；同键不同体 → 2006；窗口外作废。"""
    row = await session.scalar(
        select(IdempotencyKey).where(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key)
    )
    if row is None:
        return None
    if row.fingerprint != fingerprint:
        raise BizException(ErrorCode.IDEMPOTENCY_KEY_CONFLICT)
    if row.created_at < now_shanghai() - IDEMPOTENCY_WINDOW or row.episode_id is None:
        await session.delete(row)
        await session.commit()
        return None
    return await session.get(Episode, row.episode_id)


async def _register_idempotency(
    session: AsyncSession, user_id: int, key: str, fingerprint: str, episode_id: int
) -> None:
    session.add(
        IdempotencyKey(user_id=user_id, key=key, episode_id=episode_id, fingerprint=fingerprint)
    )
    try:
        await session.commit()
    except IntegrityError:
        # 并发同键：对端已注册，本请求按重放处理
        await session.rollback()


# ---- 创建 / 追问 / 跳过 / 重试 ----


def _check_complaint(complaint: str) -> str:
    text = complaint.strip()
    if not text:
        raise BizException(ErrorCode.COMPLAINT_EMPTY)
    if len(text) > 500:
        raise BizException(ErrorCode.COMPLAINT_TOO_LONG)
    return text


def _check_city_code(city_code: str | None) -> str | None:
    if city_code is None:
        return None
    if len(city_code) != 6 or not city_code.isdigit():
        raise BizException(ErrorCode.INVALID_PARAM, "city_code 须为 6 位行政区划码")
    return city_code


async def _require_profile(session: AsyncSession, user_id: int) -> Profile:
    profile = await session.scalar(select(Profile).where(Profile.user_id == user_id))
    if profile is None or profile.birth_date is None or profile.sex is None:
        raise BizException(ErrorCode.PROFILE_REQUIRED_MISSING)
    return profile


def _build_env(profile: Profile, city_code: str | None) -> dict[str, object] | None:
    """环境快照：M4 只有城市可用，天气接入后再补（不进本版生成模型）。"""
    code = city_code or profile.city_code
    if code is None:
        return None
    name = profile.city_name if code == profile.city_code else None
    return {
        "city_code": code,
        "city_name": name,
        "weather": None,
        "fetched_at": format_shanghai(now_shanghai()),
    }


def _initial_gate(hits: list[redflag.Hit]) -> dict[str, object]:
    return {
        "red_flags": [{"rule_id": hit.rule_id, "name": hit.name} for hit in hits],
        "citations_verified": 0,
        "citations_dropped": 0,
        "clarify_rounds": 0,
        "degraded": False,
        "fallback": False,
    }


async def create_episode(
    session: AsyncSession, user_id: int, complaint: str, city_code: str | None, key: str
) -> tuple[Episode, bool]:
    """落记录并完成红旗判定。返回 (episode, fresh)。

    fresh=False 表示幂等命中，调用方走重放流。红旗命中在这里就把结论定死：
    status=ready，不调模型，事件流只负责播报。
    """
    text = _check_complaint(complaint)
    city = _check_city_code(city_code)
    fingerprint = _fingerprint({"complaint": text, "city_code": city})

    existing = await _resolve_idempotency(session, user_id, key, fingerprint)
    if existing is not None:
        return existing, False

    profile = await _require_profile(session, user_id)
    remainder, attribution = split_attribution(text, known_terms())
    hits = redflag.detect(text)

    episode = Episode(
        user_id=user_id,
        status=STATUS_GENERATING,
        complaint_text=text,
        city_code=city,
        normalized={
            "symptom": compose.build_initial_normalized(text, attribution),
            # 主诉里已写明的时间先填上，平台就不会把用户答过的再问一遍
            **compose.build_initial_times(text, attribution),
            "site": None,
            "nature": None,
            "associated": None,
            "medications_text": None,
        },
        self_attribution=attribution,
        env=_build_env(profile, city),
        profile_snapshot=compose.map_profile_snapshot(profile),
        vitals_snapshot={},
        clarify_state={"round": 0, "round_limit": compose.CLARIFY_ROUND_LIMIT, "skipped": False},
        gate=_initial_gate(hits),
        expires_at=now_shanghai() + timedelta(days=compose.EPISODE_RETENTION_DAYS),
    )
    if hits:
        episode.status = STATUS_READY
        episode.result = compose.red_flag_result()
    session.add(episode)
    await session.commit()
    if hits:
        await _archive_with_reminder(session, episode)
        await session.commit()
    await _register_idempotency(session, user_id, key, fingerprint, episode.id)
    return episode, True


async def submit_clarify(
    session: AsyncSession,
    user_id: int,
    episode_id: int,
    answers: list[dict[str, object]],
    key: str,
) -> tuple[Episode, bool]:
    episode = await _load_owned(session, user_id, episode_id)
    if episode.status != STATUS_CLARIFYING:
        raise BizException(ErrorCode.EPISODE_STATE_NOT_ALLOWED)

    fingerprint = _fingerprint({"answers": answers})
    existing = await _resolve_idempotency(session, user_id, key, fingerprint)
    if existing is not None:
        return existing, False

    state = episode.clarify_state or {}
    question_fields = _string_list(state.get("question_fields"))
    round_ = _int_or(state.get("round"), 0)
    if round_ >= compose.CLARIFY_ROUND_LIMIT:
        raise BizException(ErrorCode.CLARIFY_ROUNDS_EXHAUSTED)

    normalized = dict(episode.normalized or {})
    seen: set[str] = set()
    for answer in answers:
        field = str(answer.get("field", ""))
        value = str(answer.get("value", ""))
        is_unknown = bool(answer.get("is_unknown", False)) or clarification.is_unknown(value)
        if field not in question_fields or field in seen:
            raise BizException(ErrorCode.CLARIFY_FIELD_INVALID)
        if not is_unknown and (not value.strip() or len(value) > 200):
            raise BizException(ErrorCode.CLARIFY_FIELD_INVALID)
        seen.add(field)
        session.add(
            EpisodeAnswer(
                episode_id=episode.id,
                round=round_,
                field=field,
                value=value.strip() or None,
                is_unknown=is_unknown,
            )
        )
        normalized[field] = compose.UNKNOWN_VALUE if is_unknown else value.strip()

    episode.normalized = normalized
    # 补充后重新执行红旗规则（16.3.4），答案视为主诉原文的延伸
    combined = (
        episode.complaint_text
        + "，"
        + "，".join(str(normalized.get(field) or "") for field in seen)
    )
    hits = redflag.detect(combined)
    if hits:
        _apply_red_flag(episode, hits)
    else:
        episode.status = STATUS_GENERATING
    await session.commit()
    if hits:
        await _archive_with_reminder(session, episode)
        await session.commit()
    await _register_idempotency(session, user_id, key, fingerprint, episode.id)
    return episode, True


async def skip_clarify(
    session: AsyncSession, user_id: int, episode_id: int, key: str
) -> tuple[Episode, bool]:
    episode = await _load_owned(session, user_id, episode_id)
    if episode.status != STATUS_CLARIFYING:
        raise BizException(ErrorCode.EPISODE_STATE_NOT_ALLOWED)

    fingerprint = _fingerprint({"skip": True})
    existing = await _resolve_idempotency(session, user_id, key, fingerprint)
    if existing is not None:
        return existing, False

    state = dict(episode.clarify_state or {})
    state["skipped"] = True
    episode.clarify_state = state
    episode.status = STATUS_GENERATING
    await session.commit()
    await _register_idempotency(session, user_id, key, fingerprint, episode.id)
    return episode, True


async def retry_episode(
    session: AsyncSession, user_id: int, episode_id: int, key: str
) -> tuple[Episode, bool]:
    episode = await _load_owned(session, user_id, episode_id)
    if episode.status != STATUS_FAILED:
        raise BizException(ErrorCode.EPISODE_STATE_NOT_ALLOWED)

    fingerprint = _fingerprint({"retry": True})
    existing = await _resolve_idempotency(session, user_id, key, fingerprint)
    if existing is not None:
        return existing, False

    episode.status = STATUS_GENERATING
    await session.commit()
    await _register_idempotency(session, user_id, key, fingerprint, episode.id)
    return episode, True


async def _archive_with_reminder(session: AsyncSession, episode: Episode) -> None:
    """生成完成即归档并按档位建提醒（issue #24）。

    引用闸门在落库前已逐字核验，让用户再「核对」是免责仪式；复查提醒挂在
    手动归档上，没点弹窗的人就静默失去闭环。归档与提醒都改为完成时自动；
    已有待处理提醒时保持原样（幂等重放不翻倍）。
    """
    triage = str((episode.result or {}).get("triage", ""))
    existing = await session.scalar(
        select(reminder_models.Reminder).where(
            reminder_models.Reminder.episode_id == episode.id,
            reminder_models.Reminder.status == reminder_models.STATUS_PENDING,
        )
    )
    if existing is None:
        reminder = create_episode_reminder(
            user_id=episode.user_id,
            episode_id=episode.id,
            created_at=episode.created_at,
            triage=triage,
            recheck_date=None,
        )
        if reminder is not None:
            session.add(reminder)
    if episode.status != STATUS_SAVED:
        episode.status = STATUS_SAVED
        episode.saved_at = now_shanghai()


def _apply_red_flag(episode: Episode, hits: list[redflag.Hit]) -> None:
    """答案里冒出红旗：结论立刻定死，之后任何模型输出都进不来。"""
    episode.status = STATUS_READY
    episode.result = compose.red_flag_result()
    gate = dict(episode.gate or {})
    gate["red_flags"] = [{"rule_id": hit.rule_id, "name": hit.name} for hit in hits]
    episode.gate = gate


# ---- 事件流 ----


def _stage(
    episode: Episode, stage: str, progress: int, text: str | None = None
) -> tuple[str, dict[str, object]]:
    return (
        "stage",
        {
            "episode_id": episode.id,
            "stage": stage,
            "text": text or compose.STAGE_TEXTS[stage],
            "progress": progress,
        },
    )


async def episode_events(
    session: AsyncSession, episode: Episode, fresh: bool
) -> AsyncIterator[tuple[str, dict[str, object]]]:
    """一次流式响应的事件源。fresh=True 跑生成管线，False 重放落库状态。

    平台类错误折成兜底结果；其余异常折成 error 事件收尾，不静默断流。
    finally 里把悬空的 generating 落成 failed，幂等重放才不会等一个死流。
    """
    try:
        if fresh:
            async for event in _pipeline(session, episode):
                yield event
        else:
            async for event in _replay(session, episode):
                yield event
    except BizException as exc:
        if int(exc.code) in PLATFORM_ERROR_CODES:
            yield _stage(episode, "compose", 95, compose.STAGE_TEXTS["degraded"])
            async for event in _finalize_fallback(session, episode):
                yield event
        else:
            yield await _fail(session, episode, int(exc.code), exc.message, retryable=True)
    except Exception:  # noqa: BLE001 - SSE 生成器不向客户端漏栈
        # 客户端只看 error 事件；栈留在服务端日志里，别把可观测性也吞了
        logger.exception("问诊生成失败 episode_id=%s", episode.id)
        yield await _fail(
            session, episode, int(ErrorCode.INTERNAL_ERROR), "服务异常", retryable=True
        )
    finally:
        if episode.status == STATUS_GENERATING:
            episode.status = STATUS_FAILED
            try:
                await session.commit()
            except Exception:  # noqa: BLE001 - 断流收尾尽力而为
                await session.rollback()


async def _fail(
    session: AsyncSession, episode: Episode, code: int, message: str, *, retryable: bool
) -> tuple[str, dict[str, object]]:
    episode.status = STATUS_FAILED
    gate = dict(episode.gate or {})
    gate["error"] = {"code": code, "message": message, "retryable": retryable}
    episode.gate = gate
    await session.commit()
    return (
        "error",
        {
            "episode_id": episode.id,
            "code": code,
            "message": message,
            "retryable": retryable,
        },
    )


async def _replay(
    session: AsyncSession, episode: Episode
) -> AsyncIterator[tuple[str, dict[str, object]]]:
    if episode.status == STATUS_GENERATING:
        # 同键并发：等首发生成收尾再整包回放
        deadline = now_shanghai().timestamp() + REPLAY_WAIT_SECONDS
        while episode.status == STATUS_GENERATING and now_shanghai().timestamp() < deadline:
            await asyncio.sleep(1)
            await session.refresh(episode)
        if episode.status == STATUS_GENERATING:
            yield await _fail(
                session, episode, int(ErrorCode.AGENTARTS_TIMEOUT), "平台超时", retryable=True
            )
            return

    if episode.status == STATUS_CLARIFYING:
        state = episode.clarify_state or {}
        yield _stage(episode, "normalize", 10)
        yield _stage(episode, "clarify", 40)
        yield (
            "question",
            {
                "episode_id": episode.id,
                "round": state.get("round", 0),
                "round_limit": state.get("round_limit", compose.CLARIFY_ROUND_LIMIT),
                "missing_fields": state.get("missing_fields", []),
                "unknown_fields": state.get("unknown_fields", []),
                "questions": state.get("questions", []),
            },
        )
        return

    if episode.status == STATUS_FAILED:
        gate = episode.gate or {}
        error = gate.get("error")
        error_map = error if isinstance(error, dict) else {}
        yield _stage(episode, "normalize", 10)
        yield (
            "error",
            {
                "episode_id": episode.id,
                "code": error_map.get("code", int(ErrorCode.INTERNAL_ERROR)),
                "message": error_map.get("message", "服务异常"),
                "retryable": True,
            },
        )
        return

    # ready / saved：整包重放
    async for event in _broadcast(episode):
        yield event


async def _pipeline(
    session: AsyncSession, episode: Episode
) -> AsyncIterator[tuple[str, dict[str, object]]]:
    """首发生成。红旗短路已在入库时定死（status=ready），这里只走模型路径。"""
    if episode.status in (STATUS_READY, STATUS_SAVED):
        async for event in _broadcast(episode):
            yield event
        return

    yield _stage(episode, "normalize", 10)
    yield _stage(episode, "retrieve", 30)

    request = compose.build_platform_request(
        episode_id=episode.id,
        request_id=f"ep{episode.id}-{uuid.uuid4().hex[:12]}",
        complaint_text=episode.complaint_text,
        normalized_public=dict(episode.normalized or {}),
        self_attribution=episode.self_attribution,
        profile_snapshot=dict(episode.profile_snapshot or {}),
        clarify_state=dict(episode.clarify_state or {}),
        red_flag_ids=[],
    )
    # 走到这里说明红旗已查无命中；matched_rule_ids 恒空
    result: dict[str, object] = {}
    task = asyncio.create_task(platform.call_triage(request, platform.fresh_session_id()))
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=HEARTBEAT_SECONDS)
            if done:
                result = task.result()
                break
            yield ("heartbeat", {"ts": format_shanghai(now_shanghai())})
    finally:
        if not task.done():
            task.cancel()

    status = str(result.get("status", ""))
    state = episode.clarify_state or {}
    # io.5 起，insufficient_evidence 恒为空检索（missing_fields 必空、字段完整性
    # 未评估），它不再携带可补问的缺项；只有 needs_clarification 表示还有字段可问
    pending = clarification.pending_fields(result, episode.normalized or {})
    can_clarify = (
        not state.get("skipped") and _int_or(state.get("round"), 0) < compose.CLARIFY_ROUND_LIMIT
    )
    if pending and can_clarify and status == "needs_clarification":
        async for event in _apply_clarification(session, episode, result):
            yield event
        return
    if status == "draft_ready":
        yield _stage(episode, "draft", 60)
        async for event in _apply_draft(session, episode, result):
            yield event
        return
    # failed / insufficient_evidence / 其它：保守兜底，不重试不追问。
    # retrieval 诊断（平台 16.3.4.x）只供排查：兜底原因记进日志与 gate
    retrieval = result.get("retrieval") if isinstance(result.get("retrieval"), dict) else None
    logger.warning(
        "平台未给出可用草稿 episode_id=%s status=%s retrieval=%s",
        episode.id,
        status,
        json.dumps(retrieval, ensure_ascii=False) if retrieval else None,
    )
    gate = dict(episode.gate or {})
    if retrieval:
        gate["retrieval"] = retrieval
        episode.gate = gate
    yield _stage(episode, "compose", 95, compose.STAGE_TEXTS["degraded"])
    async for event in _finalize_fallback(session, episode):
        yield event


async def _apply_clarification(
    session: AsyncSession, episode: Episode, result: dict[str, object]
) -> AsyncIterator[tuple[str, dict[str, object]]]:
    fields = clarification.pending_fields(result, episode.normalized or {})
    if not fields:
        yield _stage(episode, "compose", 95, compose.STAGE_TEXTS["degraded"])
        async for event in _finalize_fallback(session, episode):
            yield event
        return
    round_ = _int_or((episode.clarify_state or {}).get("round"), 0) + 1
    if round_ > compose.CLARIFY_ROUND_LIMIT:
        # 平台超过轮次上限仍在追问：按结构不合规兜底
        yield _stage(episode, "compose", 95, compose.STAGE_TEXTS["degraded"])
        async for event in _finalize_fallback(session, episode):
            yield event
        return

    missing = [clarification.FIELDS[field] for field in fields]
    fields = missing[:5]
    unknown = [
        field
        for field, value in (episode.normalized or {}).items()
        if isinstance(value, str) and clarification.is_unknown(value)
    ]
    state = dict(episode.clarify_state or {})
    state.update(
        {
            "round": round_,
            "round_limit": compose.CLARIFY_ROUND_LIMIT,
            "question_fields": fields,
            "missing_fields": missing,
            "unknown_fields": unknown,
            "questions": compose.compose_questions(fields),
        }
    )
    episode.clarify_state = state
    episode.status = STATUS_CLARIFYING
    gate = dict(episode.gate or {})
    gate["clarify_rounds"] = round_
    episode.gate = gate
    await session.commit()

    yield _stage(episode, "clarify", 40)
    yield (
        "question",
        {
            "episode_id": episode.id,
            "round": round_,
            "round_limit": compose.CLARIFY_ROUND_LIMIT,
            "missing_fields": missing,
            "unknown_fields": unknown,
            "questions": state["questions"],
        },
    )


def _as_index(value: object) -> int:
    if isinstance(value, bool):
        return -1
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    return -1


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _int_or(value: object, default: int) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else default


def _mapping_list(value: object) -> list[dict[str, object]]:
    rows = value if isinstance(value, list) else []
    return [dict(row) for row in rows if isinstance(row, dict)]


async def _apply_draft(
    session: AsyncSession, episode: Episode, result: dict[str, object]
) -> AsyncIterator[tuple[str, dict[str, object]]]:
    """后端终验（16.3.2 backend_validation_required）：科室表、词表、引用逐字核。

    平台闸门已删过一轮，这里是不信任它的第二道：核不上的一律删，
    删空不装结论。全部核完才发 citation 与结果段。
    """
    # output_list 原样落库，不过滤：引用下标必须对准平台的原始位置
    raw_pool = result.get("output_list")
    pool_rows = raw_pool if isinstance(raw_pool, list) else []
    episode.evidence_pool = pool_rows
    pool = [str(row.get("content", "")) if isinstance(row, dict) else "" for row in pool_rows]

    draft = result.get("draft")
    if not isinstance(draft, dict):
        logger.warning("草稿缺 draft 对象 episode_id=%s", episode.id)
        yield _stage(episode, "compose", 95, compose.STAGE_TEXTS["degraded"])
        async for event in _finalize_fallback(session, episode):
            yield event
        return

    kept: list[dict[str, object]] = []
    verified = 0
    dropped = 0
    raw_conditions = draft.get("conditions")
    for raw in raw_conditions if isinstance(raw_conditions, list) else []:
        if not isinstance(raw, dict):
            dropped += 1
            continue
        term = vocab_resolve(str(raw.get("name", "")))
        if term is None:
            dropped += 1
            continue
        evidence = []
        items = raw.get("evidence")
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                dropped += 1
                continue
            condition = CitationCondition(
                name=term.name,
                evidence_idx=[_as_index(item.get("evidence_idx"))],
                quote=str(item.get("quote", "")),
            )
            gate_result = verify_citations([condition], pool)
            if gate_result.kept:
                verified += 1
                evidence.append(
                    {
                        "doc_title": str(item.get("doc_title", "")),
                        "section": str(item.get("section", "")),
                        "quote": str(item.get("quote", "")),
                    }
                )
            else:
                dropped += 1
        if evidence:
            kept.append({"name": term.name, "evidence": evidence})
        else:
            dropped += 1

    composed = compose.compose_result(
        str(draft.get("triage", "")),
        str(draft.get("department_primary", "")),
        _optional_str(draft.get("department_secondary")),
        kept[:5],
    )
    if composed is None:
        logger.warning(
            "草稿档位或科室不在受控表 episode_id=%s triage=%s department=%s",
            episode.id,
            draft.get("triage"),
            draft.get("department_primary"),
        )
        yield _stage(episode, "compose", 95, compose.STAGE_TEXTS["degraded"])
        async for event in _finalize_fallback(session, episode):
            yield event
        return

    yield _stage(episode, "gate", 80)
    episode.result = composed
    gate = dict(episode.gate or {})
    gate.update(
        {
            "citations_verified": verified,
            "citations_dropped": dropped,
            "degraded": False,
            "fallback": False,
        }
    )
    episode.gate = gate
    await _archive_with_reminder(session, episode)
    await session.commit()
    async for event in _broadcast_tail(episode):
        yield event


async def _finalize_fallback(
    session: AsyncSession, episode: Episode
) -> AsyncIterator[tuple[str, dict[str, object]]]:
    """兜底：有档位有科室，不装作有依据（docs/api.md 13 节）。"""
    episode.result = compose.fallback_result()
    gate = dict(episode.gate or {})
    gate.update({"degraded": True, "fallback": True})
    episode.gate = gate
    await _archive_with_reminder(session, episode)
    await session.commit()
    async for event in _broadcast_tail(episode):
        yield event


async def _broadcast(
    episode: Episode,
) -> AsyncIterator[tuple[str, dict[str, object]]]:
    """把已落库结论按流播出：红旗短路与幂等重放共用。"""
    gate = episode.gate or {}
    red_flaged = bool(gate.get("red_flags"))
    yield _stage(episode, "normalize", 10)
    if not red_flaged:
        yield _stage(episode, "retrieve", 30)
        yield _stage(episode, "draft", 60)
    yield _stage(episode, "gate", 80)
    async for event in _broadcast_tail(episode):
        yield event


async def _broadcast_tail(
    episode: Episode,
) -> AsyncIterator[tuple[str, dict[str, object]]]:
    result = episode.result or {}
    items = _citation_items(episode)
    if items:
        yield ("citation", {"episode_id": episode.id, "items": items})
    degraded = bool(result.get("degraded"))
    if degraded:
        yield _stage(episode, "compose", 95, compose.STAGE_TEXTS["degraded"])
    else:
        yield _stage(episode, "compose", 95)
    yield (
        "result_section",
        {
            "episode_id": episode.id,
            "section": "triage",
            "payload": {
                "triage": result.get("triage"),
                "triage_label": result.get("triage_label"),
                "urgency_note": result.get("urgency_note"),
            },
        },
    )
    yield (
        "result_section",
        {
            "episode_id": episode.id,
            "section": "department",
            "payload": {
                "department_primary": result.get("department_primary"),
                "department_secondary": result.get("department_secondary"),
            },
        },
    )
    yield (
        "result_section",
        {
            "episode_id": episode.id,
            "section": "conditions",
            "payload": result.get("conditions", []),
        },
    )
    yield (
        "result_section",
        {"episode_id": episode.id, "section": "prep", "payload": result.get("prep", {})},
    )
    yield (
        "result_section",
        {"episode_id": episode.id, "section": "disclaimer", "payload": compose.DISCLAIMER},
    )
    yield (
        "done",
        {
            "episode_id": episode.id,
            "triage": result.get("triage"),
            "conditions_count": len(_mapping_list(result.get("conditions"))),
            "gate": _gate_public(episode.gate or {}),
            "degraded": degraded,
        },
    )


def _citation_items(episode: Episode) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    result = episode.result or {}
    conditions = result.get("conditions")
    for condition in conditions if isinstance(conditions, list) else []:
        if isinstance(condition, dict):
            evidence = condition.get("evidence")
            for entry in evidence if isinstance(evidence, list) else []:
                if isinstance(entry, dict):
                    items.append(dict(entry))
    return items


def _gate_public(gate: dict[str, object]) -> dict[str, object]:
    return {
        "red_flags": gate.get("red_flags", []),
        "citations_verified": gate.get("citations_verified", 0),
        "citations_dropped": gate.get("citations_dropped", 0),
        "clarify_rounds": gate.get("clarify_rounds", 0),
        "degraded": gate.get("degraded", False),
        "fallback": gate.get("fallback", False),
        # 平台 16.3.4.x 的检索诊断：只在兜底出现，值原样透传，供排查兜底原因
        "retrieval": gate.get("retrieval"),
    }


# ---- 读写端点 ----


def _summary(episode: Episode) -> dict[str, object]:
    result = episode.result or {}
    triage = result.get("triage")
    return {
        "id": episode.id,
        "status": episode.status,
        "created_at": format_shanghai(episode.created_at),
        "saved_at": format_shanghai(episode.saved_at) if episode.saved_at else None,
        "complaint_excerpt": compose.excerpt(episode.complaint_text),
        "triage": triage,
        "triage_label": compose.TRIAGE_LABELS.get(str(triage)),
        "department_primary": result.get("department_primary"),
        "degraded": bool(result.get("degraded")),
    }


async def list_episodes(
    session: AsyncSession,
    user_id: int,
    page: int,
    size: int,
    statuses: list[str],
    triages: list[str],
) -> dict[str, object]:
    query = select(Episode).where(Episode.user_id == user_id)
    if statuses:
        query = query.where(Episode.status.in_(statuses))
    if triages:
        query = query.where(func.jsonb_extract_path_text(Episode.result, "triage").in_(triages))
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        (
            await session.execute(
                query.order_by(Episode.created_at.desc()).offset((page - 1) * size).limit(size)
            )
        )
        .scalars()
        .all()
    )
    return {
        "records": [_summary(row) for row in rows],
        "total": int(total or 0),
        "page": page,
        "size": size,
    }


async def episode_detail(session: AsyncSession, user_id: int, episode_id: int) -> dict[str, object]:
    episode = await _load_owned(session, user_id, episode_id)
    state = episode.clarify_state or {}
    clarify = None
    if episode.status == STATUS_CLARIFYING:
        clarify = {
            "round": state.get("round", 0),
            "round_limit": state.get("round_limit", compose.CLARIFY_ROUND_LIMIT),
            "missing_fields": state.get("missing_fields", []),
            "unknown_fields": state.get("unknown_fields", []),
            "questions": state.get("questions", []),
        }
    return {
        "episode": {
            "id": episode.id,
            "status": episode.status,
            "created_at": format_shanghai(episode.created_at),
            "saved_at": format_shanghai(episode.saved_at) if episode.saved_at else None,
            "expires_at": format_shanghai(episode.expires_at),
            "complaint_text": episode.complaint_text,
        },
        "normalized": episode.normalized or {},
        "self_attribution": episode.self_attribution,
        "env": episode.env,
        "clarify": clarify,
        "result": episode.result,
        "gate": _gate_public(episode.gate or {}),
        "qa_turns": [],
        "profile_snapshot": episode.profile_snapshot or {},
        "vitals_snapshot": episode.vitals_snapshot or {},
        "disclaimer": compose.DISCLAIMER,
    }


async def delete_episode(session: AsyncSession, user_id: int, episode_id: int) -> None:
    episode = await _load_owned(session, user_id, episode_id)
    await session.delete(episode)
    await session.commit()


async def saved_triage_points(
    session: AsyncSession, user_id: int, since: datetime, limit: int
) -> list[dict[str, object]]:
    """已保存问诊的档位序列（档案聚合用），时间倒序取最近的 limit 条。"""
    rows = (
        (
            await session.execute(
                select(Episode)
                .where(Episode.user_id == user_id, Episode.status == STATUS_SAVED)
                .where(Episode.created_at >= since)
                .order_by(Episode.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "at": format_shanghai(row.created_at),
            "triage": (row.result or {}).get("triage"),
        }
        for row in rows
    ]


async def saved_episode_count(session: AsyncSession, user_id: int, since: datetime) -> int:
    query = (
        select(func.count())
        .select_from(Episode)
        .where(Episode.user_id == user_id, Episode.status == STATUS_SAVED)
        .where(Episode.created_at >= since)
    )
    return int(await session.scalar(query) or 0)


async def latest_saved_triage(session: AsyncSession, user_id: int) -> str | None:
    row = await session.scalar(
        select(Episode)
        .where(Episode.user_id == user_id, Episode.status == STATUS_SAVED)
        .order_by(Episode.created_at.desc())
        .limit(1)
    )
    if row is None:
        return None
    triage = (row.result or {}).get("triage")
    return str(triage) if triage else None


async def saved_symptom_texts(session: AsyncSession, user_id: int, since: datetime) -> list[str]:
    """已保存问诊的 symptom 折算文本（档案聚合的关键词统计用）。"""
    rows = (
        (
            await session.execute(
                select(Episode.normalized)
                .where(Episode.user_id == user_id, Episode.status == STATUS_SAVED)
                .where(Episode.created_at >= since)
            )
        )
        .scalars()
        .all()
    )
    texts: list[str] = []
    for normalized in rows:
        if not isinstance(normalized, dict):
            continue
        symptom = normalized.get("symptom")
        if isinstance(symptom, list):
            texts.extend(str(item) for item in symptom if isinstance(item, str))
    return texts


__all__ = [
    "create_episode",
    "delete_episode",
    "episode_detail",
    "episode_events",
    "list_episodes",
    "latest_saved_triage",
    "parse_idempotency_key",
    "retry_episode",
    "saved_episode_count",
    "saved_symptom_texts",
    "saved_triage_points",
    "skip_clarify",
    "submit_clarify",
]
