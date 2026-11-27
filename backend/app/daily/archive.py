"""健康档案摘要组装（docs/api-agentarts.md 16.8.4，docs/daily-companion.md 第 4 节）。

v1 只有两项有来源：账户档案（profile）与已保存的问诊摘要（consultations）。
`confirmed_conditions` / `medical_records` / `care_guidance` 恒为空数组——病历导入
与「已确认照护安排」实体都还没有，这里不编造：问诊结果里的候选疾病按 16.8.4
不得转成确诊，未审核的建议也不能自动标 `confirmed: true`。
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.account.models import Profile
from app.common.clock import format_shanghai
from app.episode.compose import TRIAGE_LABELS
from app.episode.models import STATUS_SAVED, Episode

# 16.8.2 的条数与每条长度上限；超限报错，不静默截断
CONSULTATION_LIMIT = 60
SUMMARY_CHARS = 800


def payload_hash(payload: Mapping[str, object]) -> str:
    """规范化 JSON 的 sha256：键排序、紧凑分隔，同输入必然同哈希。"""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _age(birth_date: date | None, on: date) -> int | None:
    if birth_date is None:
        return None
    return on.year - birth_date.year - ((on.month, on.day) < (birth_date.month, birth_date.day))


def _profile_block(row: Profile | None, report_date: date) -> dict[str, object]:
    """只放已获授权的画像字段；没有档案就整块省略，不传空壳。"""
    if row is None:
        return {}
    block: dict[str, object] = {}
    if row.name:
        block["preferred_name"] = row.name
    age = _age(row.birth_date, report_date)
    if age is not None:
        block["age"] = age
    if row.sex:
        block["sex"] = row.sex
    return block


def _consultation_summary(episode: Episode) -> str:
    """主诉、档位、科室三项事实摘要。

    与 triage 的 history_context 同构，但这里刻意不写 result.conditions：
    那是候选疾病，16.8.4 明令不得在日报档案里当确诊使用。
    """
    result = episode.result or {}
    label = TRIAGE_LABELS.get(str(result.get("triage", "")), "")
    department = str(result.get("department_primary", "") or "")
    summary = f"主诉：{episode.complaint_text}"
    if label:
        summary += f"；分诊：{label}"
    if department:
        summary += f"；建议科室：{department}"
    return summary[:SUMMARY_CHARS]


async def _saved_episodes(session: AsyncSession, user_id: int) -> Sequence[Episode]:
    query = (
        select(Episode)
        .where(Episode.user_id == user_id, Episode.status == STATUS_SAVED)
        .order_by(Episode.created_at.desc())
        .limit(CONSULTATION_LIMIT)
    )
    return (await session.execute(query)).scalars().all()


async def build_health_archive(
    session: AsyncSession, user_id: int, report_date: date
) -> dict[str, object]:
    """组装 16.8.4 的 health_archive；snapshot_id 是同一份档案的稳定指纹。"""
    profile = (
        await session.execute(select(Profile).where(Profile.user_id == user_id))
    ).scalar_one_or_none()
    episodes = await _saved_episodes(session, user_id)
    archive: dict[str, object] = {
        "profile": _profile_block(profile, report_date),
        "confirmed_conditions": [],
        "consultations": [
            {
                "id": f"ep{row.id}",
                "occurred_on": format_shanghai(row.created_at)[:10],
                "summary": _consultation_summary(row),
            }
            for row in episodes
        ],
        "medical_records": [],
        "care_guidance": [],
    }
    archive["snapshot_id"] = payload_hash(archive)
    return archive


def record_ids(archive: Mapping[str, object]) -> set[str]:
    """本次请求里可以被引用的来源 ID；used_record_ids 只允许落在其中。"""
    ids: set[str] = set()
    for key in ("confirmed_conditions", "consultations", "medical_records", "care_guidance"):
        rows = archive.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, Mapping) and isinstance(row.get("id"), str):
                ids.add(str(row["id"]))
    return ids
