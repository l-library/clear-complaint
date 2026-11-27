"""每日健康关怀业务：请求组装、本地安全标记、五种 status 分支、落库与幂等。

D3 的 router 调 `generate_daily_report` 生成、`get_daily_report` 读取；status → 信封
的映射在 router 里。信任边界在 16.8.8 第 1、3 条：用户身份由调用方传入，档案与
手表数据都由后端自己拼，前端永远不提交指标或档案字段。
"""

import json
import logging
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.clock import format_shanghai, now_shanghai
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.daily import archive as archive_module
from app.daily import mock_watch, platform
from app.daily.models import DailyReport

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "clear-complaint.daily-companion.request.v1"
TIMEZONE = "Asia/Shanghai"
DATA_SOURCE = mock_watch.DATA_SOURCE

# 16.8.2 的顶层白名单：只这九项，多一个键平台就回 invalid_input
ALLOWED_REQUEST_KEYS = frozenset(
    {
        "schema_version",
        "request_id",
        "report_date",
        "timezone",
        "data_source",
        "watch_data",
        "health_archive",
        "baseline",
        "safety_context",
    }
)
# baseline 需要同设备 7 天历史，v1 没有来源，按 16.8.5「没有就省略」不发送
REQUIRED_REQUEST_KEYS = (
    "schema_version",
    "request_id",
    "report_date",
    "timezone",
    "data_source",
    "watch_data",
    "health_archive",
    "safety_context",
)

REQUEST_CHAR_LIMIT = 180000
CONDITION_LIMIT = 30
GUIDANCE_LIMIT = 40

# 只有这四种是报告状态，回显与快照校验只对它们执行（16.8.7 末）
STATUS_READY = "ready"
STATUS_DEGRADED = "degraded"
STATUS_DATA_INSUFFICIENT = "data_insufficient"
STATUS_REVIEW_REQUIRED = "review_required"
STATUS_INVALID_INPUT = "invalid_input"
REPORT_STATUSES = frozenset(
    {STATUS_READY, STATUS_DEGRADED, STATUS_DATA_INSUFFICIENT, STATUS_REVIEW_REQUIRED}
)


def _unavailable(message: str) -> BizException:
    return BizException(ErrorCode.AGENTARTS_UNAVAILABLE, message)


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _metrics(watch_data: Mapping[str, object]) -> dict[str, Any]:
    return _mapping(watch_data.get("metrics"))


def review_reasons(watch_data: Mapping[str, object]) -> list[str]:
    """16.8.5：可用指标里的跌倒事件、ECG 设备标签需要后端安全流程接手。

    只认 quality=usable 的项；设备标签不是临床诊断，这里也只当作待核实标记。
    红旗与急诊路径不经过日报，本函数只决定「今天不生成小结」。
    """
    metrics = _metrics(watch_data)
    reasons: list[str] = []
    fall = _mapping(metrics.get("fall_detection"))
    if fall.get("detected") is True and fall.get("quality") == "usable":
        reasons.append("fall_detection")
    ecg = _mapping(metrics.get("ecg"))
    if ecg.get("recorded") is True and ecg.get("quality") == "usable":
        label = str(ecg.get("device_label", ""))
        if label in ("abnormal", "inconclusive"):
            reasons.append(f"ecg:{label}")
    return reasons


def safety_context(watch_data: Mapping[str, object]) -> dict[str, object]:
    """v1 恒不放行个体化活动/作息任务：没有「已确认照护安排」实体可以引用。"""
    return {
        "review_required": bool(review_reasons(watch_data)),
        "activity_allowed": False,
        "sleep_advice_allowed": False,
    }


def build_request(
    *,
    request_id: str,
    report_date: date,
    watch_data: Mapping[str, object],
    health_archive: Mapping[str, object],
    safety: Mapping[str, object],
) -> dict[str, object]:
    """组装 16.8.2 的九键白名单里的八项（baseline 无来源故省略）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "report_date": report_date.isoformat(),
        "timezone": TIMEZONE,
        "data_source": DATA_SOURCE,
        "watch_data": dict(watch_data),
        "health_archive": dict(health_archive),
        "safety_context": dict(safety),
    }


def _rows(value: object) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _check_limit(count: int, limit: int, field: str) -> None:
    if count > limit:
        raise BizException(ErrorCode.INVALID_PARAM, f"{field} 超过 {limit} 条上限")


def validate_request(request: Mapping[str, object]) -> None:
    """信任边界校验：白名单、必填、日期一致、条数与体积上限。

    超限一律报错，绝不静默截断后声称已读完整档案（16.8.2）。
    """
    extra = set(request) - ALLOWED_REQUEST_KEYS
    if extra:
        raise BizException(ErrorCode.INVALID_PARAM, f"请求出现白名单外的顶层字段: {sorted(extra)}")
    missing = [key for key in REQUIRED_REQUEST_KEYS if key not in request]
    if missing:
        raise BizException(ErrorCode.INVALID_PARAM, f"请求缺少必填字段: {missing}")
    report_date = str(request.get("report_date", ""))
    if str(_mapping(request.get("watch_data")).get("date", "")) != report_date:
        raise BizException(ErrorCode.INVALID_PARAM, "watch_data.date 必须与 report_date 一致")
    archive = _mapping(request.get("health_archive"))
    _check_limit(
        len(_rows(archive.get("consultations"))), archive_module.CONSULTATION_LIMIT, "consultations"
    )
    _check_limit(
        len(_rows(archive.get("medical_records"))),
        archive_module.CONSULTATION_LIMIT,
        "medical_records",
    )
    _check_limit(
        len(_rows(archive.get("confirmed_conditions"))), CONDITION_LIMIT, "confirmed_conditions"
    )
    _check_limit(len(_rows(archive.get("care_guidance"))), GUIDANCE_LIMIT, "care_guidance")
    for field in ("consultations", "medical_records"):
        for row in _rows(archive.get(field)):
            if len(str(row.get("summary", ""))) > archive_module.SUMMARY_CHARS:
                raise BizException(
                    ErrorCode.INVALID_PARAM,
                    f"{field}.summary 超过 {archive_module.SUMMARY_CHARS} 字上限",
                )
    size = len(json.dumps(request, ensure_ascii=False))
    if size > REQUEST_CHAR_LIMIT:
        raise BizException(ErrorCode.INVALID_PARAM, f"请求 JSON 超过 {REQUEST_CHAR_LIMIT} 字符上限")


def _verify_echoes(
    result: Mapping[str, object], request: Mapping[str, object], snapshot_id: str
) -> None:
    """报告状态才做的回显核对：日期、来源、档案快照必须与本次请求一致。"""
    if result.get("report_date") != request.get("report_date"):
        raise _unavailable("日报日期回显与请求不一致")
    if result.get("data_source") != request.get("data_source"):
        raise _unavailable("日报数据来源回显与请求不一致")
    if result.get("health_archive_snapshot_id") != snapshot_id:
        raise _unavailable("日报档案快照回显与本次请求不一致")


def _used_record_ids(result: Mapping[str, object], archive: Mapping[str, object]) -> list[str]:
    """只保留能在本次档案里回查到来源的 ID，编造的来源记日志后丢弃。"""
    known = archive_module.record_ids(archive)
    raw = result.get("used_record_ids")
    echoed = [item for item in raw if isinstance(item, str)] if isinstance(raw, list) else []
    verified = [item for item in echoed if item in known]
    unknown = [item for item in echoed if item not in known]
    if unknown:
        logger.warning("日报引用了档案外的来源，已丢弃: %s", unknown)
    return sorted(set(verified))


async def _current_reports(
    session: AsyncSession, user_id: int, report_date: date
) -> list[DailyReport]:
    query = select(DailyReport).where(
        DailyReport.user_id == user_id, DailyReport.report_date == report_date
    )
    return list((await session.execute(query)).scalars().all())


async def get_daily_report(
    session: AsyncSession, user_id: int, report_date: date
) -> DailyReport | None:
    """读侧取 updated_at 最新的一行：平台升版后同一天会按版本各留一行。"""
    query = (
        select(DailyReport)
        .where(DailyReport.user_id == user_id, DailyReport.report_date == report_date)
        .order_by(DailyReport.updated_at.desc())
        .limit(1)
    )
    return (await session.execute(query)).scalars().first()


def resolve_report_date(raw: str | None) -> date:
    """请求里的日期：缺省取当天，格式必须是 yyyy-MM-dd，且不得晚于今天。

    日报只总结已经发生的一天，未来日期没有可用的记录；两个接口共用这条规则。
    """
    today = now_shanghai().date()
    if not raw:
        return today
    try:
        day = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise BizException(ErrorCode.INVALID_PARAM, "report_date 必须是 yyyy-MM-dd") from None
    if day > today:
        raise BizException(ErrorCode.INVALID_PARAM, "report_date 不得晚于今天")
    return day


def report_payload(row: DailyReport) -> dict[str, Any]:
    """落库行 → 对外字段；`degraded` 由内部 status 折出，前端不必自己判断字符串。"""
    return {
        "report_date": row.report_date.isoformat(),
        "status": row.status,
        "degraded": row.status == STATUS_DEGRADED,
        "data_source": row.data_source,
        "workflow_version": row.workflow_version,
        "summary": row.summary,
        "data_quality": row.data_quality,
        "used_record_ids": list(row.used_record_ids or []),
        "created_at": format_shanghai(row.created_at),
        "updated_at": format_shanghai(row.updated_at),
    }


async def persist_report(
    session: AsyncSession,
    *,
    user_id: int,
    report_date: date,
    started_at: datetime,
    workflow_version: str,
    status: str,
    summary: dict[str, Any] | None,
    data_quality: dict[str, Any] | None,
    used_record_ids: list[str] | None,
    input_snapshot_hash: str,
) -> DailyReport:
    """同（用户＋日期＋版本）更新覆盖；迟到结果不覆盖更新的报告（16.8.8 第 6 条）。

    started_at 是本次生成的起始时刻：若库里已有在它之后写过的行，说明有更新
    的一次生成已经落库，本次结果迟到，丢弃并返回库里那份。
    """
    rows = await _current_reports(session, user_id, report_date)
    newest = max(rows, key=lambda row: row.updated_at) if rows else None
    if newest is not None and newest.updated_at > started_at:
        logger.warning(
            "日报迟到结果被丢弃 user_id=%s date=%s status=%s stored=%s",
            user_id,
            report_date,
            status,
            newest.status,
        )
        return newest

    current = next((row for row in rows if row.workflow_version == workflow_version), None)
    if current is None:
        current = DailyReport(
            user_id=user_id,
            report_date=report_date,
            workflow_version=workflow_version,
            data_source=DATA_SOURCE,
        )
        session.add(current)
    current.status = status
    current.summary = summary
    current.data_quality = data_quality
    current.used_record_ids = used_record_ids
    current.input_snapshot_hash = input_snapshot_hash
    await session.commit()
    await session.refresh(current)
    return current


async def generate_daily_report(
    session: AsyncSession, *, user_id: int, report_date: date | None = None
) -> DailyReport:
    """生成一份当日报告并落库，返回落库后的行。

    五种 status 的处理：
    - ready / degraded / data_insufficient：核对回显后落库；
    - review_required：本地设备标记命中时短路，不调平台；平台自己判定的照常落库；
    - invalid_input：不落库，抛业务错误（16.8.8：不当成正常报告保存）。
    """
    day = report_date or now_shanghai().date()
    started_at = now_shanghai()
    health_archive = await archive_module.build_health_archive(session, user_id, day)
    watch_data = mock_watch.build_watch_data(user_id, day)
    reasons = review_reasons(watch_data)
    safety = safety_context(watch_data)
    input_snapshot_hash = archive_module.payload_hash(
        {"watch_data": watch_data, "health_archive": health_archive, "safety_context": safety}
    )

    if reasons:
        # 平台在同一条件下同样跳过模型，本地先把这一天标成待核实：调用只会白等
        # 60 秒并得到同一结论；同时用这一行覆盖今天可能已有的旧小结，避免用户在
        # 设备已报跌倒/异常心电标签后仍看到一份「ready」的日常鼓励。
        logger.info(
            "日报本地短路 review_required user_id=%s date=%s reasons=%s", user_id, day, reasons
        )
        return await persist_report(
            session,
            user_id=user_id,
            report_date=day,
            started_at=started_at,
            workflow_version="",
            status=STATUS_REVIEW_REQUIRED,
            summary=None,
            data_quality=None,
            used_record_ids=None,
            input_snapshot_hash=input_snapshot_hash,
        )

    request = build_request(
        request_id=f"daily-{user_id}-{day.isoformat()}-{uuid4().hex[:12]}",
        report_date=day,
        watch_data=watch_data,
        health_archive=health_archive,
        safety=safety,
    )
    validate_request(request)

    result = await platform.call_daily(request, platform.fresh_session_id())
    status = str(result.get("status", ""))

    if status == STATUS_INVALID_INPUT:
        # 空壳形状见 16.8.7 末：summary=null、data_quality={}、data_source=unknown、
        # report_date=""。这里只读 error_code，不解析正文，也不落库。
        logger.warning(
            "日报输入被平台拒绝 user_id=%s date=%s error_code=%s request_id=%s",
            user_id,
            day,
            result.get("error_code"),
            result.get("request_id"),
        )
        raise BizException(ErrorCode.DAILY_INVALID_INPUT, "日报输入未通过平台校验")
    if status not in REPORT_STATUSES:
        raise _unavailable(f"日报返回未知 status: {status or '空'}")

    _verify_echoes(result, request, str(health_archive["snapshot_id"]))
    summary = result.get("summary")
    return await persist_report(
        session,
        user_id=user_id,
        report_date=day,
        started_at=started_at,
        workflow_version=str(result.get("workflow_version") or ""),
        status=status,
        summary=summary if isinstance(summary, dict) else None,
        data_quality=_mapping(result.get("data_quality")),
        used_record_ids=_used_record_ids(result, health_archive),
        input_snapshot_hash=input_snapshot_hash,
    )
