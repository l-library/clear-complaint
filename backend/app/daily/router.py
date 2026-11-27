"""日报路由：生成当日报告与读取当日报告。前缀只在 main.py 出现一次。

status → 信封：`ready`/`degraded` 成功返回（`degraded=true` 带降级标记）；
`data_insufficient`/`review_required` 抛各自的业务码；`invalid_input` 由 service
直接抛错且不落库。用户身份只从令牌取，手表指标与档案字段一律不由前端提交
（docs/api-agentarts.md 16.8.8 第 1 条）。
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.account import service as account_service
from app.account.models import User
from app.common.api import ApiResponse, ok
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.daily import schema, service
from app.daily.models import DailyReport
from app.db.session import get_session

router = APIRouter(tags=["daily"])

CurrentUser = Annotated[User, Depends(account_service.get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]

# 两种"合法但不出报告"的状态各有自己的码；报告状态不在此表里，正常返回
_REFUSED_STATUS_CODES: dict[str, ErrorCode] = {
    service.STATUS_DATA_INSUFFICIENT: ErrorCode.DAILY_DATA_INSUFFICIENT,
    service.STATUS_REVIEW_REQUIRED: ErrorCode.DAILY_REVIEW_REQUIRED,
}


def _report_envelope(row: DailyReport) -> ApiResponse[schema.DailyReportOut]:
    """落库行 → 信封：先序列化再判拒绝码。

    `review_required` 的行 `summary` 为 null（本地短路由安全流程接手，没有正文），
    序列化必须容得下，否则这一状态会以 500 代替业务码。
    """
    if row.status not in service.REPORT_STATUSES:
        raise BizException(ErrorCode.AGENTARTS_UNAVAILABLE, f"日报 status 不认识: {row.status}")
    payload = schema.DailyReportOut(**service.report_payload(row))
    refusal = _REFUSED_STATUS_CODES.get(row.status)
    if refusal is not None:
        raise BizException(refusal)
    return ok(payload)


@router.post("/daily/generate")
async def generate_daily(
    session: SessionDep,
    user: CurrentUser,
    payload: Annotated[schema.DailyGenerateRequest | None, Body()] = None,
) -> ApiResponse[schema.DailyReportOut]:
    """非流式生成，平台单次调用预算 60 秒（客户端超时表），业务层不重试。

    同日重复调用按当前档案与合成数据重算并覆盖同一行，不产生第二条当前报告。
    """
    day = service.resolve_report_date(payload.report_date if payload else None)
    row = await service.generate_daily_report(session, user_id=user.id, report_date=day)
    return _report_envelope(row)


@router.get("/daily")
async def get_daily(
    session: SessionDep,
    user: CurrentUser,
    date: Annotated[str, Query()] = "",
) -> ApiResponse[schema.DailyReportOut]:
    """读某一天的当前报告；平台升版后同日有多行时取最新写入的一份。"""
    day = service.resolve_report_date(date)
    row = await service.get_daily_report(session, user.id, day)
    if row is None:
        raise BizException(ErrorCode.DAILY_REPORT_NOT_FOUND)
    return _report_envelope(row)
