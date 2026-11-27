"""日报测试的公共构件：落库快照、平台返回体构造、档案与问诊种子。

tests/ 本身不是包（没有 __init__.py），pytest 把 tests/daily 当成顶层包，所以
用例按 `daily.support` 导入，与运行时的模块名一致。
"""

from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.account.models import Profile, User
from app.common.clock import now_shanghai
from app.daily import mock_watch, platform, service
from app.daily.models import DailyReport
from app.episode.models import Episode

RunDb = Callable[[Callable[[AsyncSession], Awaitable[Any]]], Any]

DAY = date(2026, 11, 23)
WORKFLOW_VERSION = "2026-11-24.daily-companion.2"


def snapshot(row: DailyReport) -> dict[str, Any]:
    """把 ORM 行折成普通 dict：用例不必在关掉的会话上碰懒加载属性。"""
    return {
        "id": row.id,
        "user_id": row.user_id,
        "report_date": row.report_date,
        "workflow_version": row.workflow_version,
        "data_source": row.data_source,
        "status": row.status,
        "summary": row.summary,
        "data_quality": row.data_quality,
        "used_record_ids": row.used_record_ids,
        "input_snapshot_hash": row.input_snapshot_hash,
        "updated_at": row.updated_at,
    }


def generate(run_db: RunDb, user_id: int, report_date: date = DAY) -> dict[str, Any]:
    async def op(session: AsyncSession) -> dict[str, Any]:
        row = await service.generate_daily_report(session, user_id=user_id, report_date=report_date)
        return snapshot(row)

    return dict(run_db(op))


def stored(run_db: RunDb, user_id: int) -> list[dict[str, Any]]:
    async def op(session: AsyncSession) -> list[dict[str, Any]]:
        query = (
            select(DailyReport)
            .where(DailyReport.user_id == user_id)
            .order_by(DailyReport.updated_at)
        )
        return [snapshot(row) for row in (await session.execute(query)).scalars().all()]

    return list(run_db(op))


def make_user(run_db: RunDb, phone: str = "13800000002") -> int:
    async def op(session: AsyncSession) -> int:
        user = User(phone=phone, password_hash="synthetic$not-a-real-hash")
        session.add(user)
        await session.commit()
        return user.id

    return int(run_db(op))


def add_profile(
    run_db: RunDb,
    user_id: int,
    *,
    name: str | None = "演示用户",
    birth_date: date | None = date(1958, 3, 4),
    sex: str | None = "female",
) -> None:
    async def op(session: AsyncSession) -> None:
        session.add(Profile(user_id=user_id, name=name, birth_date=birth_date, sex=sex))
        await session.commit()

    run_db(op)


def add_episode(
    run_db: RunDb,
    user_id: int,
    *,
    status: str = "saved",
    complaint: str = "近三天咳嗽，夜间明显",
    result: dict[str, Any] | None = None,
    created_at: datetime | None = None,
) -> int:
    async def op(session: AsyncSession) -> int:
        moment = created_at or now_shanghai()
        episode = Episode(
            user_id=user_id,
            status=status,
            complaint_text=complaint,
            result=result if result is not None else _CLINIC_RESULT,
            created_at=moment,
            expires_at=moment + timedelta(days=30),
        )
        session.add(episode)
        await session.commit()
        return episode.id

    return int(run_db(op))


_CLINIC_RESULT: dict[str, Any] = {
    "triage": "clinic",
    "department_primary": "呼吸内科",
    # 候选疾病：16.8.4 明令不得进日报档案，用例用它验证没被写进摘要
    "conditions": [{"name": "社区获得性肺炎", "evidence": []}],
}


def platform_result(
    business_request: Mapping[str, object],
    *,
    status: str = "ready",
    workflow_version: str = WORKFLOW_VERSION,
    summary: object | None = None,
    data_quality: object | None = None,
    used_record_ids: list[str] | None = None,
    echo: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """按 16.8.7 造一份报告状态返回；回显默认与本次请求一致。"""
    if summary is None:
        summary = {
            "title": "今天的健康小结（合成）",
            "greeting": "今天辛苦了。",
            "highlights": [],
            "health_connections": [],
            "gentle_reminders": [],
            "tomorrow_actions": [],
            "closing": "照顾好自己。",
            "limitations": "单日设备记录不能判断疾病变化。",
        }
    if data_quality is None:
        data_quality = {
            "wear_minutes": 1380,
            "available_metric_ids": ["steps"],
            "coverage_limited": False,
        }
    result: dict[str, Any] = {
        "schema_version": "clear-complaint.daily-companion.workflow.v1",
        "workflow_version": workflow_version,
        "request_id": business_request.get("request_id"),
        "report_date": business_request.get("report_date"),
        "data_source": business_request.get("data_source"),
        "status": status,
        "summary": summary,
        "rendered_text": "【模拟数据演示】",
        "metric_overview": [],
        "data_quality": data_quality,
        "health_archive_snapshot_id": _snapshot_id(business_request),
        "used_record_ids": used_record_ids if used_record_ids is not None else [],
        "model_selection_applied": status == "ready",
        "needs_backend_review": status == "review_required",
        "backend_validation_required": True,
        "error_code": "",
    }
    result.update(echo or {})
    return result


def invalid_input_result(business_request: Mapping[str, object]) -> dict[str, Any]:
    """16.8.7 末的失败空壳：正文全空、来源 unknown、日期空串，request_id 照常回显。"""
    return {
        "schema_version": "clear-complaint.daily-companion.workflow.v1",
        "workflow_version": WORKFLOW_VERSION,
        "request_id": business_request.get("request_id"),
        "report_date": "",
        "data_source": "unknown",
        "status": "invalid_input",
        "summary": None,
        "rendered_text": "",
        "metric_overview": [],
        "data_quality": {},
        "health_archive_snapshot_id": "",
        "used_record_ids": [],
        "model_selection_applied": False,
        "needs_backend_review": False,
        "backend_validation_required": True,
        "error_code": "INVALID_REQUEST",
    }


def _snapshot_id(business_request: Mapping[str, object]) -> object:
    archive = business_request.get("health_archive")
    return archive.get("snapshot_id") if isinstance(archive, Mapping) else None


def stub_platform(
    monkeypatch: pytest.MonkeyPatch,
    factory: Callable[[Mapping[str, object]], dict[str, Any]],
) -> list[dict[str, object]]:
    """把 app.daily.platform.call_daily 换成记录入参的桩，返回已调用请求列表。"""
    calls: list[dict[str, object]] = []

    async def fake(
        business_request: Mapping[str, object], platform_session_id: str
    ) -> dict[str, object]:
        calls.append(dict(business_request))
        return factory(business_request)

    monkeypatch.setattr(platform, "call_daily", fake)
    return calls


def watch_data_with(user_id: int, report_date: date = DAY, **metrics: object) -> dict[str, Any]:
    """以合成数据为底，替换若干指标：用来构造跌倒/异常心电这类待核实场景。"""
    watch = mock_watch.build_watch_data(user_id, report_date)
    base = watch.get("metrics")
    merged: dict[str, object] = dict(base) if isinstance(base, dict) else {}
    merged.update(metrics)
    return {**watch, "metrics": merged}
