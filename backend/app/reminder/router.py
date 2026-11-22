"""提醒路由：按日列表与响应。前缀只在 main.py 出现一次。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.account import service as account_service
from app.account.models import User
from app.common.api import ApiResponse, ok
from app.common.clock import now_shanghai
from app.db.session import get_session
from app.reminder import schema, service

router = APIRouter(tags=["reminder"])

CurrentUser = Annotated[User, Depends(account_service.get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/reminders")
async def list_reminders(
    session: SessionDep,
    user: CurrentUser,
    date: Annotated[str, Query()] = "",
    kind: Annotated[str | None, Query()] = None,
) -> ApiResponse[schema.ReminderListData]:
    day = date or now_shanghai().strftime("%Y-%m-%d")
    data = await service.list_reminders(session, user.id, day, kind)
    return ok(schema.ReminderListData(**data))


@router.post("/reminders/{reminder_id}/respond")
async def respond_reminder(
    reminder_id: int,
    payload: schema.ReminderRespond,
    session: SessionDep,
    user: CurrentUser,
) -> ApiResponse[schema.ReminderRespondData]:
    data = await service.respond(session, user.id, reminder_id, payload.model_dump())
    return ok(schema.ReminderRespondData(**data))
