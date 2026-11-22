"""进程内定时任务：不引 Redis，一个循环按序跑所有作业。

作业全部幂等：重复执行不产生重复行。默认关闭（Settings.scheduler_enabled），
生产与本地演示经 .env 打开；测试与 CI 不开，避免后台写库串扰用例。

作业清单（api.md 14.1）：
- 用药提醒生成：活跃计划按时刻出当天的提醒，dedupe_key 防重
- 短期药到期：ended_on 过期的置 expired，计划一并停用
- 提醒超时：过期待办标 missed（口径：due_at 超过 24 小时）
- 未保存清理：到期问诊物理删除
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from datetime import time as clock_time

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.archive.models import Medication, MedicationPlan
from app.common.clock import now_shanghai
from app.db.session import SessionLocal
from app.episode.models import STATUS_SAVED, Episode
from app.reminder import models as reminder_models

logger = logging.getLogger(__name__)

TICK_SECONDS = 60
MEDICATION_REMINDER_BODY = "你录入的用法，请按医嘱或说明书使用。"


async def generate_medication_reminders(session: AsyncSession, day: date) -> int:
    """活跃计划 × 当天时刻 → 用药提醒。dedupe_key 保证重复执行不翻倍。"""
    rows = (
        await session.execute(
            select(MedicationPlan, Medication)
            .join(Medication, MedicationPlan.medication_id == Medication.id)
            .where(
                MedicationPlan.status == "active",
                Medication.status == "active",
                MedicationPlan.started_on <= day,
                MedicationPlan.ended_on >= day,
            )
        )
    ).all()
    created = 0
    for plan, medication in rows:
        for raw_time in plan.times or []:
            dedupe_key = f"med:{plan.id}:{day.isoformat()}:{raw_time}"
            exists = await session.scalar(
                select(reminder_models.Reminder.id).where(
                    reminder_models.Reminder.dedupe_key == dedupe_key
                )
            )
            if exists is not None:
                continue
            hour, minute = raw_time.split(":")
            due_at = datetime.combine(
                day, clock_time(int(hour), int(minute)), tzinfo=now_shanghai().tzinfo
            )
            dosage = medication.dosage_text or ""
            title = f"{medication.name} {dosage}".strip()
            session.add(
                reminder_models.Reminder(
                    user_id=plan.user_id,
                    episode_id=None,
                    kind=reminder_models.KIND_MEDICATION,
                    status=reminder_models.STATUS_PENDING,
                    due_at=due_at,
                    title=title[:100],
                    body=MEDICATION_REMINDER_BODY,
                    dedupe_key=dedupe_key,
                )
            )
            created += 1
    if created:
        await session.commit()
    return created


async def expire_short_term_medications(session: AsyncSession, today: date) -> int:
    """短期药过了 ended_on：置 expired，计划一并停用。"""
    expired = await session.execute(
        update(Medication)
        .where(
            Medication.kind == "short_term",
            Medication.status == "active",
            Medication.ended_on < today,
        )
        .values(status="expired")
        .returning(Medication.id)
    )
    ids = expired.scalars().all()
    if ids:
        await session.execute(
            update(MedicationPlan)
            .where(MedicationPlan.medication_id.in_(ids))
            .values(status="stopped")
        )
        await session.commit()
    return len(ids)


async def mark_overdue_missed(session: AsyncSession, now: datetime) -> int:
    """过期待办标 missed。口径选了 24 小时：当天还能补，隔天算错过。"""
    result = await session.execute(
        update(reminder_models.Reminder)
        .where(
            reminder_models.Reminder.status == reminder_models.STATUS_PENDING,
            reminder_models.Reminder.due_at < now - timedelta(hours=24),
        )
        .values(status=reminder_models.STATUS_MISSED)
        .returning(reminder_models.Reminder.id)
    )
    count = len(result.scalars().all())
    await session.commit()
    return count


async def purge_expired_episodes(session: AsyncSession, now: datetime) -> int:
    """未保存问诊到期物理删除（30 天保留期由 expires_at 判定）。"""
    ids = (
        (
            await session.execute(
                select(Episode.id).where(Episode.expires_at < now, Episode.status != STATUS_SAVED)
            )
        )
        .scalars()
        .all()
    )
    if ids:
        await session.execute(delete(Episode).where(Episode.id.in_(ids)))
        await session.commit()
    return len(ids)


async def run_tick(session: AsyncSession) -> None:
    now = now_shanghai()
    await generate_medication_reminders(session, now.date())
    await expire_short_term_medications(session, now.date())
    await mark_overdue_missed(session, now)
    await purge_expired_episodes(session, now)


async def run_forever(interval: int = TICK_SECONDS) -> None:
    """应用生命周期里的后台循环；单次作业失败只记日志，不打断循环。"""
    while True:
        try:
            async with SessionLocal() as session:
                await run_tick(session)
        except Exception:  # noqa: BLE001 - 后台作业不许带崩进程
            logger.exception("定时任务执行失败")
        await asyncio.sleep(interval)
