"""数据导出：全量 JSON + 问诊 CSV 打包成 zip，一次性令牌下载。

zip 写在 EXPORT_DIR 下，令牌行只记录有效期与已用标记；下载不鉴权，
靠不可猜测的 token 本身。序列化不走各域的响应模型，直接从 ORM 行取数，
保证导出是"落库事实"的快照而不是接口形状的副本。
"""

from __future__ import annotations

import csv
import io
import json
import logging
import secrets
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.account.models import Consent, ExportToken, Profile, User
from app.archive.models import Medication, MedicationPlan, Vital
from app.common.clock import format_shanghai, now_shanghai
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.core.config import get_settings
from app.episode.models import Episode, EpisodeAnswer
from app.reminder import models as reminder_models

logger = logging.getLogger(__name__)

EXPORT_VALID = timedelta(hours=24)
EXPORT_MAX_BYTES = 50 * 1024 * 1024

_EXPORT_KEYS = (
    "user",
    "profile",
    "consent",
    "vitals",
    "medications",
    "medication_plans",
    "episodes",
    "reminders",
    "followup_records",
)


def _export_dir() -> Path:
    settings = get_settings()
    if not settings.export_dir:
        raise BizException(ErrorCode.INTERNAL_ERROR, "服务端未配置 EXPORT_DIR")
    directory = Path(settings.export_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _ts(moment: datetime | None) -> str | None:
    return format_shanghai(moment) if moment is not None else None


async def _collect(session: AsyncSession, user: User) -> dict[str, Any]:
    """全量取数。问诊行内联追问回答；引用随 result/证据池一起导出。"""
    profile = await session.scalar(select(Profile).where(Profile.user_id == user.id))
    consent = await session.scalar(
        select(Consent).where(Consent.user_id == user.id).order_by(Consent.created_at.desc())
    )
    vitals = (
        (
            await session.execute(
                select(Vital).where(Vital.user_id == user.id).order_by(Vital.measured_at.asc())
            )
        )
        .scalars()
        .all()
    )
    medications = (
        (
            await session.execute(
                select(Medication)
                .where(Medication.user_id == user.id)
                .order_by(Medication.id.asc())
            )
        )
        .scalars()
        .all()
    )
    plans = (
        (
            await session.execute(
                select(MedicationPlan)
                .where(MedicationPlan.user_id == user.id)
                .order_by(MedicationPlan.id.asc())
            )
        )
        .scalars()
        .all()
    )
    episodes = (
        (
            await session.execute(
                select(Episode).where(Episode.user_id == user.id).order_by(Episode.id.asc())
            )
        )
        .scalars()
        .all()
    )
    answers = (
        (
            await session.execute(
                select(EpisodeAnswer).where(
                    EpisodeAnswer.episode_id.in_([episode.id for episode in episodes])
                )
            )
        )
        .scalars()
        .all()
    )
    reminders = (
        (
            await session.execute(
                select(reminder_models.Reminder).where(reminder_models.Reminder.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    followups = (
        (
            await session.execute(
                select(reminder_models.FollowupRecord).where(
                    reminder_models.FollowupRecord.user_id == user.id
                )
            )
        )
        .scalars()
        .all()
    )

    answers_by_episode: dict[int, list[dict[str, Any]]] = {}
    for answer in answers:
        answers_by_episode.setdefault(answer.episode_id, []).append(
            {
                "round": answer.round,
                "field": answer.field,
                "value": answer.value,
                "is_unknown": answer.is_unknown,
                "created_at": _ts(answer.created_at),
            }
        )

    return {
        "exported_at": format_shanghai(now_shanghai()),
        "user": {"id": user.id, "phone": user.phone, "created_at": _ts(user.created_at)},
        "profile": (
            {
                "name": profile.name,
                "birth_date": profile.birth_date.isoformat() if profile.birth_date else None,
                "sex": profile.sex,
                "city_code": profile.city_code,
                "city_name": profile.city_name,
                "conditions": profile.conditions,
                "condition_note": profile.condition_note,
                "allergies": profile.allergies,
                "allergy_note": profile.allergy_note,
                "updated_at": _ts(profile.updated_at),
            }
            if profile is not None
            else None
        ),
        "consent": (
            {
                "version": consent.version,
                "sensitive_accepted": consent.sensitive_accepted,
                "created_at": _ts(consent.created_at),
            }
            if consent is not None
            else None
        ),
        "vitals": [
            {
                "id": row.id,
                "kind": row.kind,
                "measured_at": _ts(row.measured_at),
                "height_cm": float(row.height_cm) if row.height_cm is not None else None,
                "weight_kg": float(row.weight_kg) if row.weight_kg is not None else None,
                "systolic": row.systolic,
                "diastolic": row.diastolic,
                "pulse": row.pulse,
            }
            for row in vitals
        ],
        "medications": [
            {
                "id": row.id,
                "name": row.name,
                "dosage_text": row.dosage_text,
                "frequency_text": row.frequency_text,
                "kind": row.kind,
                "started_on": row.started_on.isoformat(),
                "ended_on": row.ended_on.isoformat() if row.ended_on else None,
                "status": row.status,
            }
            for row in medications
        ],
        "medication_plans": [
            {
                "id": row.id,
                "medication_id": row.medication_id,
                "times": list(row.times or []),
                "started_on": row.started_on.isoformat(),
                "ended_on": row.ended_on.isoformat() if row.ended_on else None,
                "status": row.status,
                "note": row.note,
            }
            for row in plans
        ],
        "episodes": [
            {
                "id": row.id,
                "status": row.status,
                "complaint_text": row.complaint_text,
                "created_at": _ts(row.created_at),
                "saved_at": _ts(row.saved_at),
                "expires_at": _ts(row.expires_at),
                "normalized": row.normalized,
                "self_attribution": row.self_attribution,
                "env": row.env,
                "profile_snapshot": row.profile_snapshot,
                "vitals_snapshot": row.vitals_snapshot,
                "evidence_pool": row.evidence_pool,
                "result": row.result,
                "gate": row.gate,
                "clarify_state": row.clarify_state,
                "answers": answers_by_episode.get(row.id, []),
            }
            for row in episodes
        ],
        "reminders": [
            {
                "id": row.id,
                "kind": row.kind,
                "status": row.status,
                "due_at": _ts(row.due_at),
                "title": row.title,
                "body": row.body,
                "snooze_count": row.snooze_count,
                "episode_id": row.episode_id,
            }
            for row in reminders
        ],
        "followup_records": [
            {
                "id": row.id,
                "reminder_id": row.reminder_id,
                "episode_id": row.episode_id,
                "answers": row.answers,
                "note": row.note,
                "advice_level": row.advice_level,
                "advice_text": row.advice_text,
                "supplement": row.supplement,
                "degraded": row.degraded,
                "created_at": _ts(row.created_at),
            }
            for row in followups
        ],
        # 受限问答尚未落地（api.md 5.10），导出里保留字段位置
        "qa_turns": [],
    }


def _episodes_csv(episodes: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(
        ["id", "status", "created_at", "triage", "department_primary", "complaint_text"]
    )
    for episode in episodes:
        result = episode.get("result") or {}
        writer.writerow(
            [
                episode["id"],
                episode["status"],
                episode["created_at"] or "",
                result.get("triage", ""),
                result.get("department_primary", ""),
                episode["complaint_text"],
            ]
        )
    return buffer.getvalue()


async def build_export(session: AsyncSession, user: User) -> dict[str, Any]:
    """同步打包并登记一次性令牌。超过 50MB 拒绝（api.md 11.1 的 3005）。"""
    data = await _collect(session, user)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data.json", json.dumps(data, ensure_ascii=False, indent=2))
        archive.writestr("episodes.csv", _episodes_csv(data["episodes"]))
    size = payload.getbuffer().nbytes
    if size > EXPORT_MAX_BYTES:
        raise BizException(ErrorCode.EXPORT_TOO_LARGE)

    token = secrets.token_urlsafe(32)
    path = _export_dir() / f"{token}.zip"
    path.write_bytes(payload.getbuffer())
    expires_at = now_shanghai() + EXPORT_VALID
    session.add(ExportToken(user_id=user.id, token=token, size_bytes=size, expires_at=expires_at))
    await session.commit()
    return {
        "url": f"/api/export/{token}",
        "expires_at": format_shanghai(expires_at),
        "size_bytes": size,
    }


async def fetch_export(session: AsyncSession, token: str) -> Path:
    """按令牌取包：不存在 / 已用 / 已过期一律 404，不泄露任何状态。"""
    row = await session.scalar(select(ExportToken).where(ExportToken.token == token))
    if row is None or row.used_at is not None or row.expires_at < now_shanghai():
        raise BizException(ErrorCode.NOT_FOUND)
    claimed = await session.execute(
        update(ExportToken)
        .where(ExportToken.token == token, ExportToken.used_at.is_(None))
        .values(used_at=now_shanghai())
        .returning(ExportToken.id)
    )
    if claimed.scalar_one_or_none() is None:
        # 并发下载：先到先得
        raise BizException(ErrorCode.NOT_FOUND)
    await session.commit()
    path = _export_dir() / f"{token}.zip"
    if not path.exists():
        raise BizException(ErrorCode.NOT_FOUND)
    return path


async def purge_export_tokens(session: AsyncSession, user_id: int) -> int:
    """数据/账号删除时连带清掉导出令牌与文件，不留可下载的个人数据。"""
    rows = (
        (await session.execute(select(ExportToken).where(ExportToken.user_id == user_id)))
        .scalars()
        .all()
    )
    directory = _export_dir()
    for row in rows:
        path = directory / f"{row.token}.zip"
        if path.exists():
            path.unlink()
    await session.execute(delete(ExportToken).where(ExportToken.user_id == user_id))
    await session.commit()
    return len(rows)


async def purge_expired_exports(session: AsyncSession, now: datetime) -> int:
    """定时任务：过期导出的行与文件一并清掉。"""
    rows = (
        (
            await session.execute(
                select(ExportToken).where(ExportToken.expires_at < now - EXPORT_VALID)
            )
        )
        .scalars()
        .all()
    )
    directory = _export_dir()
    for row in rows:
        path = directory / f"{row.token}.zip"
        if path.exists():
            path.unlink()
    await session.execute(delete(ExportToken).where(ExportToken.id.in_([row.id for row in rows])))
    await session.commit()
    return len(rows)
