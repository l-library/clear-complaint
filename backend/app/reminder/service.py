"""提醒业务。M4 只覆盖问诊保存触发的创建；列表与响应端点在 M6。

档位到提醒的映射来自 docs/api.md 5.7：self_observe 建 followup（+48 小时）、
clinic 建 recheck（3–14 天内的指定日，缺省 +3 天）、emergency 忽略。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.clock import now_shanghai
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.reminder import models as m

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
