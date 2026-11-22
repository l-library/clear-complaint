"""档案业务：体征与用药的校验、增删改查。

数值边界是边界输入校验（非协商项），全部在服务层显式抛 3002/3003，
不靠 pydantic 默认报错兜底——那样错误码与文案都对不上。
"""

import re
from collections import Counter
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.account.service import get_profile
from app.agent.normalize import COLLOQUIAL_MAP
from app.archive.models import Medication, MedicationPlan, Vital
from app.common.clock import format_shanghai, now_shanghai
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.episode import service as episode_service
from app.reminder import service as reminder_service

_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

VITAL_KINDS = ("height", "weight", "bp")
MEDICATION_KINDS = ("long_term", "short_term")
MEDICATION_STATUSES = ("active", "stopped")

# docs/api.md 7.2 的数值范围；None 表示该 kind 下此列选填
_VITAL_FIELDS: dict[str, dict[str, tuple[int, int] | None]] = {
    "height": {"height_cm": (50, 250)},
    "weight": {"weight_kg": (2, 300)},
    "bp": {"systolic": (60, 260), "diastolic": (30, 160), "pulse": (30, 220)},
}
_VALUE_COLUMNS = ("height_cm", "weight_kg", "systolic", "diastolic", "pulse")


def _parse_date(raw: str, field: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise BizException(ErrorCode.MEDICATION_INVALID, f"{field} 须为 yyyy-MM-dd") from None


def _parse_measured_at(raw: str) -> datetime:
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        raise BizException(ErrorCode.VITAL_OUT_OF_RANGE, "measured_at 须为合法时间") from None
    if moment.tzinfo is None:
        raise BizException(ErrorCode.VITAL_OUT_OF_RANGE, "measured_at 须带时区")
    if moment > now_shanghai():
        raise BizException(ErrorCode.VITAL_OUT_OF_RANGE, "measured_at 不能晚于当前时间")
    return moment


def _check_vital_values(kind: str, values: Mapping[str, object]) -> dict[str, object]:
    """按 kind 校验对应列；kind 用不到的列一律置 null。"""
    if kind not in VITAL_KINDS:
        raise BizException(ErrorCode.VITAL_OUT_OF_RANGE, "kind 须为 height/weight/bp")
    cleaned: dict[str, object] = {column: None for column in _VALUE_COLUMNS}
    for field, limits in _VITAL_FIELDS[kind].items():
        value = values.get(field)
        if value is None:
            # 脉搏选填；其余在各自 kind 下必填
            if limits is not None and field != "pulse":
                raise BizException(ErrorCode.VITAL_OUT_OF_RANGE, f"{field} 不能为空")
            continue
        number = float(value)  # type: ignore[arg-type]
        if limits is not None and not limits[0] <= number <= limits[1]:
            raise BizException(
                ErrorCode.VITAL_OUT_OF_RANGE, f"{field} 须在 {limits[0]} 到 {limits[1]} 之间"
            )
        cleaned[field] = value
    return cleaned


# ---- 体征 ----


def _vital_out(vital: Vital) -> dict[str, object]:
    def num(value: object) -> float | None:
        return float(value) if value is not None else None  # type: ignore[arg-type]

    return {
        "id": vital.id,
        "kind": vital.kind,
        "measured_at": format_shanghai(vital.measured_at),
        "height_cm": num(vital.height_cm),
        "weight_kg": num(vital.weight_kg),
        "systolic": vital.systolic,
        "diastolic": vital.diastolic,
        "pulse": vital.pulse,
        "created_at": format_shanghai(vital.created_at),
    }


async def _load_owned_vital(session: AsyncSession, user_id: int, vital_id: int) -> Vital:
    vital = await session.get(Vital, vital_id)
    if vital is None or vital.user_id != user_id:
        raise BizException(ErrorCode.NOT_FOUND, "体征记录不存在")
    return vital


async def create_vital(
    session: AsyncSession,
    user_id: int,
    kind: str,
    measured_at: str,
    values: Mapping[str, object],
) -> dict[str, object]:
    cleaned = _check_vital_values(kind, values)
    moment = _parse_measured_at(measured_at)
    if kind == "height":
        # 身高单值语义：旧身高删掉只留最新一条（api.md 7.2）
        await session.execute(delete(Vital).where(Vital.user_id == user_id, Vital.kind == "height"))
    vital = Vital(user_id=user_id, kind=kind, measured_at=moment, **cleaned)
    session.add(vital)
    await session.commit()
    return _vital_out(vital)


async def list_vitals(
    session: AsyncSession, user_id: int, kind: str | None, page: int, size: int
) -> dict[str, object]:
    query = select(Vital).where(Vital.user_id == user_id)
    if kind is not None:
        query = query.where(Vital.kind == kind)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        (
            await session.execute(
                query.order_by(Vital.measured_at.desc()).offset((page - 1) * size).limit(size)
            )
        )
        .scalars()
        .all()
    )
    return {
        "records": [_vital_out(row) for row in rows],
        "total": int(total or 0),
        "page": page,
        "size": size,
    }


async def update_vital(
    session: AsyncSession,
    user_id: int,
    vital_id: int,
    values: Mapping[str, object],
    fields: set[str],
) -> dict[str, object]:
    vital = await _load_owned_vital(session, user_id, vital_id)
    merged: dict[str, object] = {
        "height_cm": vital.height_cm,
        "weight_kg": vital.weight_kg,
        "systolic": vital.systolic,
        "diastolic": vital.diastolic,
        "pulse": vital.pulse,
    }
    for field in _VALUE_COLUMNS:
        if field in fields:
            merged[field] = values.get(field)
    if "measured_at" in fields and values.get("measured_at") is not None:
        vital.measured_at = _parse_measured_at(str(values["measured_at"]))
    cleaned = _check_vital_values(vital.kind, merged)
    for column, value in cleaned.items():
        setattr(vital, column, value)
    await session.commit()
    return _vital_out(vital)


async def delete_vital(session: AsyncSession, user_id: int, vital_id: int) -> None:
    vital = await _load_owned_vital(session, user_id, vital_id)
    await session.delete(vital)
    await session.commit()


# ---- 用药 ----


def _text_or_none(text: str | None) -> str | None:
    return text.strip() or None if text is not None else None


def _medication_out(medication: Medication) -> dict[str, object]:
    return {
        "id": medication.id,
        "name": medication.name,
        "dosage_text": medication.dosage_text,
        "frequency_text": medication.frequency_text,
        "kind": medication.kind,
        "started_on": medication.started_on.isoformat(),
        "ended_on": medication.ended_on.isoformat() if medication.ended_on else None,
        "status": medication.status,
        "created_at": format_shanghai(medication.created_at),
    }


async def _load_owned_medication(
    session: AsyncSession, user_id: int, medication_id: int
) -> Medication:
    medication = await session.get(Medication, medication_id)
    if medication is None or medication.user_id != user_id:
        raise BizException(ErrorCode.NOT_FOUND, "用药记录不存在")
    return medication


async def create_medication(
    session: AsyncSession,
    user_id: int,
    name: str,
    dosage_text: str | None,
    frequency_text: str | None,
    kind: str,
    started_on: str,
    ended_on: str | None,
) -> dict[str, object]:
    if kind not in MEDICATION_KINDS:
        raise BizException(ErrorCode.MEDICATION_INVALID, "kind 须为 long_term/short_term")
    start = _parse_date(started_on, "started_on")
    end = _parse_date(ended_on, "ended_on") if ended_on is not None else None
    if kind == "short_term" and end is None:
        raise BizException(ErrorCode.MEDICATION_INVALID, "short_term 用药必须填 ended_on")
    if end is not None and end < start:
        raise BizException(ErrorCode.MEDICATION_INVALID, "ended_on 不能早于 started_on")
    medication = Medication(
        user_id=user_id,
        name=name.strip(),
        dosage_text=_text_or_none(dosage_text),
        frequency_text=_text_or_none(frequency_text),
        kind=kind,
        started_on=start,
        ended_on=end,
    )
    session.add(medication)
    await session.commit()
    return _medication_out(medication)


async def list_medications(
    session: AsyncSession, user_id: int, kind: str | None, status: str | None
) -> dict[str, object]:
    query = select(Medication).where(Medication.user_id == user_id)
    if kind is not None:
        query = query.where(Medication.kind == kind)
    if status is not None:
        query = query.where(Medication.status == status)
    rows = (
        (
            await session.execute(
                query.order_by(Medication.status.asc(), Medication.started_on.desc())
            )
        )
        .scalars()
        .all()
    )
    return {"records": [_medication_out(row) for row in rows]}


async def update_medication(
    session: AsyncSession,
    user_id: int,
    medication_id: int,
    values: Mapping[str, object],
    fields: set[str],
) -> dict[str, object]:
    medication = await _load_owned_medication(session, user_id, medication_id)
    if "name" in fields and values.get("name") is not None:
        medication.name = str(values["name"]).strip()
    for field in ("dosage_text", "frequency_text"):
        if field in fields:
            raw = values.get(field)
            setattr(medication, field, _text_or_none(str(raw) if raw is not None else None))
    if "ended_on" in fields:
        raw = values.get("ended_on")
        medication.ended_on = _parse_date(str(raw), "ended_on") if raw is not None else None
    if medication.ended_on is not None and medication.ended_on < medication.started_on:
        raise BizException(ErrorCode.MEDICATION_INVALID, "ended_on 不能早于 started_on")
    if "status" in fields:
        status = values.get("status")
        if status not in MEDICATION_STATUSES:
            raise BizException(ErrorCode.MEDICATION_INVALID, "status 须为 active/stopped")
        medication.status = str(status)
        if status == "stopped":
            # 停药连坐计划（api.md 8.3）
            await session.execute(
                update(MedicationPlan)
                .where(MedicationPlan.medication_id == medication.id)
                .values(status="stopped")
            )
    await session.commit()
    return _medication_out(medication)


async def delete_medication(session: AsyncSession, user_id: int, medication_id: int) -> None:
    medication = await _load_owned_medication(session, user_id, medication_id)
    # 连带删除计划；未处理用药提醒由 reminder 表的外键级联接管
    await session.execute(
        delete(MedicationPlan).where(MedicationPlan.medication_id == medication.id)
    )
    await session.delete(medication)
    await session.commit()


# ---- 用药计划 ----


def _check_times(times: list[str]) -> list[str]:
    seen: set[str] = set()
    for raw in times:
        if _TIME.fullmatch(raw) is None:
            raise BizException(ErrorCode.MEDICATION_INVALID, "times 须为 HH:mm 格式")
        if raw in seen:
            raise BizException(ErrorCode.MEDICATION_INVALID, "times 不能重复")
        seen.add(raw)
    return sorted(times)


def _plan_out(plan: MedicationPlan) -> dict[str, object]:
    return {
        "id": plan.id,
        "medication_id": plan.medication_id,
        "times": list(plan.times or []),
        "started_on": plan.started_on.isoformat(),
        "ended_on": plan.ended_on.isoformat() if plan.ended_on else None,
        "status": plan.status,
        "note": plan.note,
        "created_at": format_shanghai(plan.created_at),
    }


async def _load_owned_plan(session: AsyncSession, user_id: int, plan_id: int) -> MedicationPlan:
    plan = await session.get(MedicationPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise BizException(ErrorCode.NOT_FOUND, "用药计划不存在")
    return plan


async def create_plan(
    session: AsyncSession,
    user_id: int,
    medication_id: int,
    times: list[str],
    started_on: str,
    ended_on: str | None,
    note: str | None,
) -> dict[str, object]:
    await _load_owned_medication(session, user_id, medication_id)
    start = _parse_date(started_on, "started_on")
    # 缺省 ended_on 为 started_on + 30 天（api.md 8.5）
    end = _parse_date(ended_on, "ended_on") if ended_on is not None else start + timedelta(days=30)
    if end < start:
        raise BizException(ErrorCode.MEDICATION_INVALID, "ended_on 不能早于 started_on")
    plan = MedicationPlan(
        user_id=user_id,
        medication_id=medication_id,
        times=_check_times(times),
        started_on=start,
        ended_on=end,
        note=note,
    )
    session.add(plan)
    await session.commit()
    return _plan_out(plan)


async def list_plans(session: AsyncSession, user_id: int) -> dict[str, object]:
    rows = (
        (
            await session.execute(
                select(MedicationPlan)
                .where(MedicationPlan.user_id == user_id)
                .order_by(MedicationPlan.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return {"records": [_plan_out(row) for row in rows]}


async def update_plan(
    session: AsyncSession,
    user_id: int,
    plan_id: int,
    values: Mapping[str, object],
    fields: set[str],
) -> dict[str, object]:
    plan = await _load_owned_plan(session, user_id, plan_id)
    if "times" in fields and values.get("times") is not None:
        raw = values["times"]
        if not isinstance(raw, list):
            raise BizException(ErrorCode.MEDICATION_INVALID, "times 须为字符串数组")
        plan.times = _check_times([str(item) for item in raw])
    if "started_on" in fields and values.get("started_on") is not None:
        plan.started_on = _parse_date(str(values["started_on"]), "started_on")
    if "ended_on" in fields:
        raw = values.get("ended_on")
        plan.ended_on = _parse_date(str(raw), "ended_on") if raw is not None else None
    if plan.ended_on is not None and plan.ended_on < plan.started_on:
        raise BizException(ErrorCode.MEDICATION_INVALID, "ended_on 不能早于 started_on")
    if "note" in fields:
        raw = values.get("note")
        plan.note = str(raw) if raw is not None else None
    if "status" in fields:
        status = values.get("status")
        if status not in MEDICATION_STATUSES:
            raise BizException(ErrorCode.MEDICATION_INVALID, "status 须为 active/stopped")
        plan.status = str(status)
    await session.commit()
    return _plan_out(plan)


async def delete_plan(session: AsyncSession, user_id: int, plan_id: int) -> None:
    plan = await _load_owned_plan(session, user_id, plan_id)
    await session.delete(plan)
    await session.commit()


__all__ = [
    "create_medication",
    "create_plan",
    "create_vital",
    "delete_medication",
    "delete_plan",
    "delete_vital",
    "list_medications",
    "list_plans",
    "list_vitals",
    "update_medication",
    "update_plan",
    "update_vital",
]


# ---- 档案聚合（docs/api.md 第 9 节） ----


async def _latest_vital(session: AsyncSession, user_id: int, kind: str) -> Vital | None:
    return await session.scalar(
        select(Vital)
        .where(Vital.user_id == user_id, Vital.kind == kind)
        .order_by(Vital.measured_at.desc())
        .limit(1)
    )


def _bmi(height_cm: object, weight_kg: object) -> float | None:
    if not isinstance(height_cm, (int, float, Decimal)) or not isinstance(
        weight_kg, (int, float, Decimal)
    ):
        return None
    meters = float(height_cm) / 100
    return round(float(weight_kg) / (meters * meters), 1)


async def overview(session: AsyncSession, user_id: int) -> dict[str, object]:
    """档案首页一次性取数（api.md 9.1），避免首屏多次请求。"""
    profile = await get_profile(session, user_id)
    height = await _latest_vital(session, user_id, "height")
    weight = await _latest_vital(session, user_id, "weight")
    bp = await _latest_vital(session, user_id, "bp")
    since_90d = now_shanghai() - timedelta(days=90)

    latest_bp = None
    if bp is not None:
        latest_bp = {
            "measured_at": format_shanghai(bp.measured_at),
            "systolic": bp.systolic,
            "diastolic": bp.diastolic,
            "pulse": bp.pulse,
        }
    return {
        "profile": profile.model_dump() if profile is not None else None,
        "vitals": {
            "latest_height_cm": (
                float(height.height_cm)
                if height is not None and height.height_cm is not None
                else None
            ),
            "latest_weight_kg": (
                float(weight.weight_kg)
                if weight is not None and weight.weight_kg is not None
                else None
            ),
            "bmi": _bmi(
                height.height_cm if height is not None else None,
                weight.weight_kg if weight is not None else None,
            ),
            "latest_bp": latest_bp,
        },
        "trend_summary": {
            "episodes_90d": await episode_service.saved_episode_count(session, user_id, since_90d),
            "latest_triage": await episode_service.latest_saved_triage(session, user_id),
        },
        "pending": await reminder_service.pending_counts(session, user_id),
    }


async def trend(session: AsyncSession, user_id: int, days: int, limit: int) -> dict[str, object]:
    """趋势取数（api.md 9.2）。三个点序列都取最近 limit 条后按时间升序返回。"""
    since = now_shanghai() - timedelta(days=days)

    triage_rows = await episode_service.saved_triage_points(session, user_id, since, limit)

    weight_rows = (
        (
            await session.execute(
                select(Vital)
                .where(Vital.user_id == user_id, Vital.kind == "weight")
                .where(Vital.measured_at >= since)
                .order_by(Vital.measured_at.desc())
                .limit(limit * 3)  # 同日多测要先去重再截断
            )
        )
        .scalars()
        .all()
    )
    weight_by_day: dict[str, float] = {}
    for row in sorted(weight_rows, key=lambda item: item.measured_at):
        if row.weight_kg is not None:
            weight_by_day[row.measured_at.date().isoformat()] = float(row.weight_kg)
    weight_points = [
        {"at": day, "weight_kg": value} for day, value in sorted(weight_by_day.items())
    ][-limit:]

    bp_rows = (
        (
            await session.execute(
                select(Vital)
                .where(Vital.user_id == user_id, Vital.kind == "bp")
                .where(Vital.measured_at >= since)
                .order_by(Vital.measured_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    bp_points = [
        {
            "at": format_shanghai(row.measured_at),
            "systolic": row.systolic,
            "diastolic": row.diastolic,
        }
        for row in sorted(bp_rows, key=lambda item: item.measured_at)
    ]

    # 关键词：symptom 目前存的是归一化后的整句折算文本（字段级抽取未落地），
    # 可统计的受控症状词面取自归一化映射表的临床词侧（流涕、腹泻、胸痛……）。
    # 抽取落地后 symptom 变成词条列表，这条统计自然收敛为逐词计数。
    counter: Counter[str] = Counter()
    surfaces = sorted(
        {clinical for _, clinical in COLLOQUIAL_MAP if len(clinical) >= 2},
        key=len,
        reverse=True,
    )
    for text in await episode_service.saved_symptom_texts(session, user_id, since):
        for surface in surfaces:
            if surface in text:
                counter[surface] += 1

    return {
        "triage_points": triage_rows,
        "weight_points": weight_points,
        "bp_points": bp_points,
        "symptom_keywords": [
            {"term": term, "count": count} for term, count in counter.most_common(5)
        ],
    }


__all__.extend(["overview", "trend"])
