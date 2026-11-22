"""提醒业务：创建（问诊保存触发）、按日列表与响应（随访 / 复查 / 用药）。

随访两层（api.md 10.2）：第一层是固定八条优先级规则表给档位与文案，
安全优先——红旗命中（含 note 文本）恒为急诊；第二层 supplement 只在
clinic 档生成，超时或校验不过整层为 null，响应仍是成功。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import redflag
from app.agent.normalize import COLLOQUIAL_MAP
from app.common.clock import format_shanghai, now_shanghai
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.episode.models import Episode
from app.reminder import models as m
from app.reminder import platform

logger = logging.getLogger(__name__)

RECHECK_EARLIEST_DAYS = 3
RECHECK_LATEST_DAYS = 14
RECHECK_HOUR = time(9, 0)
FOLLOWUP_AFTER = timedelta(hours=48)
# 八条规则键 → 16.5.1 的 reason 枚举（平台只认这四个 clinic 语义）
PLATFORM_REASON: dict[str, str] = {
    "worse": "worsened",
    "new_symptom_not_visited": "new_symptom",
    "new_symptom_visited": "worsened_after_visit",
    "not_relieved_not_visited": "not_relieved",
    "not_relieved_visited": "worsened_after_visit",
}

SNOOZE_STEP = timedelta(hours=1)
SNOOZE_LIMIT = 2
FOLLOWUP_CALL_TIMEOUT = 8.0

# 随访第一层：固定八条优先级规则，自上而下首条命中即用。
# 安全优先：红旗恒急诊；闭合类规则放最后。
FOLLOWUP_RULES: tuple[tuple[str, str, str], ...] = (
    ("red_flag", "emergency", "出现需要立即处理的征象，请立即就医"),
    ("worse", "clinic", "症状较上次加重，建议尽快就诊"),
    ("new_symptom_not_visited", "clinic", "出现新的不适，建议就诊评估"),
    ("new_symptom_visited", "clinic", "已就诊但仍有新的不适，建议复诊"),
    ("not_relieved_not_visited", "clinic", "症状未缓解，建议尽快就诊"),
    ("not_relieved_visited", "clinic", "已就诊但症状未缓解，建议复诊"),
    ("relieved", "closed", "症状已好转，本次随访结束"),
    ("visited", "closed", "已就诊，本次随访结束"),
)

RECHECK_EARLIEST_DAYS = 3
RECHECK_LATEST_DAYS = 14
RECHECK_HOUR = time(9, 0)
FOLLOWUP_AFTER = timedelta(hours=48)


def _recheck_due(created_at: datetime, recheck_date: str | None) -> datetime:
    """recheck_date（yyyy-MM-dd）须落在 created_at + 3..14 天，缺省 +3 天。"""
    if recheck_date is None or recheck_date == "":
        due_date = (created_at + timedelta(days=RECHECK_EARLIEST_DAYS)).date()
    else:
        try:
            due_date = date.fromisoformat(recheck_date)
        except ValueError:
            raise BizException(ErrorCode.INVALID_PARAM, "recheck_date 须为 yyyy-MM-dd") from None
    earliest = (created_at + timedelta(days=RECHECK_EARLIEST_DAYS)).date()
    latest = (created_at + timedelta(days=RECHECK_LATEST_DAYS)).date()
    if not earliest <= due_date <= latest:
        raise BizException(
            ErrorCode.INVALID_PARAM,
            f"recheck_date 须在 {earliest.isoformat()} 到 {latest.isoformat()} 之间",
        )
    return datetime.combine(due_date, RECHECK_HOUR, tzinfo=now_shanghai().tzinfo)


def create_episode_reminder(
    *,
    user_id: int,
    episode_id: int,
    created_at: datetime,
    triage: str,
    recheck_date: str | None,
) -> m.Reminder | None:
    """按档位创建提醒，只构造不落库（调用方统一提交，保证原子性）。

    emergency 与未知档位返回 None：api.md 5.7 的"忽略该字段"，不猜提醒。
    """
    if triage == "emergency":
        return None
    if triage == "self_observe":
        return m.Reminder(
            user_id=user_id,
            episode_id=episode_id,
            kind=m.KIND_FOLLOWUP,
            status=m.STATUS_PENDING,
            due_at=created_at + FOLLOWUP_AFTER,
            title="上次不适的复评提醒",
            body="到时间了，请复评这次不适；症状加重或出现新情况，立即前往急诊。",
        )
    if triage == "clinic":
        return m.Reminder(
            user_id=user_id,
            episode_id=episode_id,
            kind=m.KIND_RECHECK,
            status=m.STATUS_PENDING,
            due_at=_recheck_due(created_at, recheck_date),
            title="门诊就诊提醒",
            body="按问诊建议尽快就诊，带上问诊记录与正在服用的药物清单。",
        )
    return None


async def pending_counts(session: AsyncSession, user_id: int) -> dict[str, int]:
    """按 kind 数待处理提醒（档案聚合用）。未处理不等于未到期，口径就是 status=pending。"""
    rows = (
        await session.execute(
            select(m.Reminder.kind, func.count())
            .where(m.Reminder.user_id == user_id, m.Reminder.status == m.STATUS_PENDING)
            .group_by(m.Reminder.kind)
        )
    ).all()
    counts = {kind: int(count) for kind, count in rows}
    return {
        "total": sum(counts.values()),
        "medication": counts.get(m.KIND_MEDICATION, 0),
        "followup": counts.get(m.KIND_FOLLOWUP, 0),
        "recheck": counts.get(m.KIND_RECHECK, 0),
    }


# ---- 按日列表（api.md 10.1） ----


def _reminder_out(row: m.Reminder) -> dict[str, object]:
    return {
        "id": row.id,
        "kind": row.kind,
        "due_at": format_shanghai(row.due_at),
        "status": row.status,
        "title": row.title,
        "body": row.body,
        "snooze_count": row.snooze_count,
    }


async def list_reminders(
    session: AsyncSession, user_id: int, day: str, kind: str | None
) -> dict[str, object]:
    """按日返回三组提醒，不给分页。文案已由后端模板拼装。"""
    try:
        target = date.fromisoformat(day)
    except ValueError:
        raise BizException(ErrorCode.INVALID_PARAM, "date 须为 yyyy-MM-dd") from None
    start = datetime.combine(target, time(0, 0), tzinfo=now_shanghai().tzinfo)
    end = start + timedelta(days=1)

    query = select(m.Reminder).where(
        m.Reminder.user_id == user_id,
        m.Reminder.due_at >= start,
        m.Reminder.due_at < end,
    )
    if kind is not None:
        query = query.where(m.Reminder.kind == kind)
    rows = (await session.execute(query.order_by(m.Reminder.due_at.asc()))).scalars().all()

    groups: dict[str, list[dict[str, object]]] = {
        "medication": [],
        "followup": [],
        "recheck": [],
    }
    pending = 0
    for row in rows:
        if row.status == m.STATUS_PENDING:
            pending += 1
        groups.setdefault(row.kind, []).append(_reminder_out(row))
    return {"groups": groups, "pending_count": pending}


# ---- 响应（api.md 10.2） ----


async def _load_owned(session: AsyncSession, user_id: int, reminder_id: int) -> m.Reminder:
    row = await session.get(m.Reminder, reminder_id)
    if row is None or row.user_id != user_id:
        raise BizException(ErrorCode.REMINDER_NOT_FOUND_OR_DONE, "提醒不存在")
    return row


async def respond(
    session: AsyncSession, user_id: int, reminder_id: int, payload: Mapping[str, object]
) -> dict[str, object]:
    row = await _load_owned(session, user_id, reminder_id)
    if row.status != m.STATUS_PENDING:
        raise BizException(ErrorCode.REMINDER_NOT_FOUND_OR_DONE, "提醒已处理", http_status=409)
    action = str(payload.get("action", ""))

    if row.kind == m.KIND_FOLLOWUP:
        return await _respond_followup(session, user_id, row, payload, action)
    if row.kind == m.KIND_RECHECK:
        data = _respond_recheck(row, action)
    elif row.kind == m.KIND_MEDICATION:
        data = _respond_medication(row, action)
    else:
        raise BizException(ErrorCode.REMINDER_NOT_FOUND_OR_DONE, "提醒不存在")
    # recheck 与 medication 路径在此统一提交（followup 在自己的流程里已提交）
    await session.commit()
    return data


def _respond_recheck(row: m.Reminder, action: str) -> dict[str, object]:
    if action == "visited" or action == "improved":
        row.status = m.STATUS_DONE
    elif action == "planned":
        row.status = m.STATUS_PENDING  # 还没去但要安排：保留待办
    else:
        raise BizException(ErrorCode.INVALID_PARAM, "recheck 动作须为 visited/planned/improved")
    return {"status": row.status}


def _respond_medication(row: m.Reminder, action: str) -> dict[str, object]:
    if action == "taken" or action == "skipped":
        row.status = m.STATUS_DONE
        return {"status": row.status}
    if action == "snooze":
        if row.snooze_count >= SNOOZE_LIMIT:
            raise BizException(ErrorCode.REMINDER_NOT_FOUND_OR_DONE, "提醒已处理", http_status=409)
        row.snooze_count += 1
        row.due_at = now_shanghai() + SNOOZE_STEP
        row.status = m.STATUS_PENDING
        return {"status": row.status, "due_at": format_shanghai(row.due_at)}
    raise BizException(ErrorCode.INVALID_PARAM, "medication 动作须为 taken/skipped/snooze")


def _check_followup_answers(payload: Mapping[str, object]) -> tuple[dict[str, str], str]:
    if str(payload.get("action", "")) != "answer":
        raise BizException(ErrorCode.INVALID_PARAM, "followup 动作须为 answer")
    raw = payload.get("answers")
    answers_raw = raw if isinstance(raw, dict) else {}
    answers: dict[str, str] = {}
    for key, allowed in (
        ("relieved", ("yes", "no", "worse")),
        ("visited", ("yes", "no")),
        ("new_symptom", ("yes", "no")),
    ):
        value = str(answers_raw.get(key, ""))
        if value not in allowed:
            raise BizException(ErrorCode.INVALID_PARAM, f"answers.{key} 取值不合法")
        answers[key] = value
    note_raw = payload.get("note")
    note = str(note_raw) if note_raw is not None else ""
    if len(note) > 200:
        raise BizException(ErrorCode.INVALID_PARAM, "note 不能超过 200 字")
    return answers, note


def _apply_followup_rules(answers: Mapping[str, str], note: str) -> tuple[str, str, str]:
    """八条规则表按序判定。红旗先于一切：note 里冒出红旗词直接急诊。"""
    if redflag.detect(note):
        level, text = "emergency", "出现需要立即处理的征象，请立即就医"
        return level, text, "red_flag"
    markers = {
        "worse": answers.get("relieved") == "worse",
        "new_symptom_not_visited": answers.get("new_symptom") == "yes"
        and answers.get("visited") == "no",
        "new_symptom_visited": answers.get("new_symptom") == "yes"
        and answers.get("visited") == "yes",
        "not_relieved_not_visited": answers.get("relieved") == "no"
        and answers.get("visited") == "no",
        "not_relieved_visited": answers.get("relieved") == "no" and answers.get("visited") == "yes",
        "relieved": answers.get("relieved") == "yes",
        "visited": answers.get("visited") == "yes",
    }
    for reason, level, text in FOLLOWUP_RULES:
        if reason == "red_flag":
            continue
        if markers.get(reason):
            return level, text, reason
    # answers 全部合法时不可能走到这里；保守给观察档
    return "self_observe", "继续观察，症状加重再就诊", "fallback"


def _followup_catalogs(symptom_text: str) -> dict[str, object]:
    """第二层的受控目录。观察项来自归一化映射表的临床词面 + 两条通用项。"""
    surfaces = sorted(
        {clinical for _, clinical in COLLOQUIAL_MAP if len(clinical) >= 2},
        key=len,
        reverse=True,
    )
    watch_for = [
        {"id": f"obs-{index}", "text": f"{surface}是否仍存在或加重"}
        for index, surface in enumerate(surface for surface in surfaces if surface in symptom_text)
    ]
    watch_for.append({"id": f"obs-{len(watch_for)}", "text": "日常活动是否受影响"})
    questions = [{"id": "q-0", "text": "这次不适对日常活动有什么影响？"}]
    return {
        "version": "clear-complaint.followup.catalog.v1",
        "watch_for": watch_for,
        "questions": questions,
    }


def _flattened_prep(result: Mapping[str, object]) -> list[str]:
    """prepare_idx 的全局下标口径：bring 全部 → describe 全部 → go_now 全部（16.5.3）。"""
    prep = result.get("prep")
    items: list[str] = []
    if not isinstance(prep, dict):
        return items
    for group in ("bring", "describe", "go_now"):
        entries = prep.get(group)
        if isinstance(entries, list):
            items.extend(str(entry) for entry in entries if isinstance(entry, str))
    return items


async def _build_supplement_request(
    episode: Episode,
    answers: Mapping[str, str],
    note: str,
    level: str,
    reason: str,
    text: str,
    followup_id: int,
) -> dict[str, object]:
    normalized = episode.normalized or {}
    symptom_raw = normalized.get("symptom")
    symptom = " ".join(str(item) for item in (symptom_raw if isinstance(symptom_raw, list) else []))
    return {
        "schema_version": "clear-complaint.followup-supplement.request.v1",
        "episode_id": str(episode.id),
        "followup_id": str(followup_id),
        "request_id": f"fu{followup_id}-{reason}",
        "first_layer": {
            "level": level,
            "reason": PLATFORM_REASON.get(reason, reason),
            "text": text,
        },
        "answers": dict(answers),
        "note": note,
        "normalized_snapshot": {"symptom": symptom, "duration": normalized.get("duration_text")},
        "original_result": {
            "triage": (episode.result or {}).get("triage"),
            "department_primary": (episode.result or {}).get("department_primary"),
            "prep": (episode.result or {}).get("prep", {}),
        },
        "catalogs": _followup_catalogs(symptom),
    }


def _validate_supplement(
    raw: object, catalog: Mapping[str, object], prep_items: list[str]
) -> dict[str, object] | None:
    """第二层校验：watch_for 只能来自本轮目录，prepare_idx 须落在展开表内。"""
    if not isinstance(raw, dict):
        return None
    catalog_watch = catalog.get("watch_for")
    allowed_texts = {
        str(entry.get("text", ""))
        for entry in (catalog_watch if isinstance(catalog_watch, list) else [])
        if isinstance(entry, dict)
    }
    watch_for = raw.get("watch_for")
    kept_watch = [
        str(item)
        for item in (watch_for if isinstance(watch_for, list) else [])
        if str(item) in allowed_texts
    ]
    prepare_idx_raw = raw.get("prepare_idx")
    seen_idx: set[int] = set()
    kept_idx: list[int] = []
    for item in prepare_idx_raw if isinstance(prepare_idx_raw, list) else []:
        if isinstance(item, bool) or not isinstance(item, (int, str)):
            continue
        index = int(item)
        if 0 <= index < len(prep_items) and index not in seen_idx:
            seen_idx.add(index)
            kept_idx.append(index)
    question = raw.get("next_question")
    if not isinstance(question, str) or not question.strip():
        return None
    if not kept_watch:
        return None
    return {"watch_for": kept_watch, "prepare_idx": kept_idx, "next_question": question.strip()}


async def _respond_followup(
    session: AsyncSession,
    user_id: int,
    row: m.Reminder,
    payload: Mapping[str, object],
    action: str,
) -> dict[str, object]:
    answers, note = _check_followup_answers(payload)
    level, text, reason = _apply_followup_rules(answers, note)
    row.status = m.STATUS_DONE

    record = m.FollowupRecord(
        user_id=user_id,
        reminder_id=row.id,
        episode_id=row.episode_id,
        answers=dict(answers),
        note=note or None,
        advice_level=level,
        advice_text=text,
    )
    session.add(record)

    supplement: dict[str, object] | None = None
    if level == "clinic" and row.episode_id is not None:
        episode = await session.get(Episode, row.episode_id)
        # 16.5.1 适用条件：只有自我观察档的问诊才有随访补充；
        # clinic 走复查提醒、emergency 不建随访
        if episode is not None and (episode.result or {}).get("triage") == "self_observe":
            # 先拿记录主键，第二层请求的 followup_id 才能对上落库行
            await session.flush()
            supplement = await _generate_supplement(
                episode, answers, note, level, reason, text, record.id
            )
    if level == "clinic" and supplement is None:
        record.degraded = True
    record.supplement = supplement
    await session.commit()

    data: dict[str, object] = {
        "status": row.status,
        "advice": {"level": level, "text": text},
        "supplement": supplement,
    }
    return data


async def _generate_supplement(
    episode: Episode,
    answers: Mapping[str, str],
    note: str,
    level: str,
    reason: str,
    text: str,
    followup_id: int,
) -> dict[str, object] | None:
    """第二层：超时或校验不过整层为 null，主流程不能因此失败（16.2.4）。"""
    request = await _build_supplement_request(
        episode, answers, note, level, reason, text, followup_id
    )
    catalogs = request["catalogs"]
    if not isinstance(catalogs, dict):
        return None
    prep_items = _flattened_prep(episode.result or {})
    try:
        result = await asyncio.wait_for(
            platform.call_followup(request, platform.fresh_session_id()),
            timeout=FOLLOWUP_CALL_TIMEOUT,
        )
    except Exception:  # noqa: BLE001 - 第二层失败不影响第一层结论
        logger.warning("随访第二层调用失败 episode_id=%s", episode.id)
        return None
    if str(result.get("status", "")) != "supplement_ready":
        return None
    return _validate_supplement(result.get("supplement"), catalogs, prep_items)
