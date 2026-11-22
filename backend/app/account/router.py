"""账号路由：注册、登录、刷新、登出与隐私政策元信息。

路径不带 /api 前缀，前缀只在 main.py 出现一次。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.account import schema, service
from app.account.models import User
from app.common.api import ApiResponse, ok
from app.core.config import get_settings
from app.db.session import get_session

router = APIRouter(tags=["account"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(service.get_current_user)]


@router.post("/auth/register")
async def register(
    payload: schema.RegisterRequest, session: SessionDep
) -> ApiResponse[schema.AuthData]:
    return ok(await service.register(session, payload))


@router.post("/auth/login")
async def login(payload: schema.LoginRequest, session: SessionDep) -> ApiResponse[schema.AuthData]:
    return ok(await service.login(session, payload))


@router.post("/auth/refresh")
async def refresh(
    payload: schema.RefreshRequest, session: SessionDep
) -> ApiResponse[schema.RefreshData]:
    tokens = await service.refresh_tokens(session, payload.refresh_token)
    return ok(schema.RefreshData(tokens=tokens))


@router.post("/auth/logout")
async def logout(
    payload: schema.RefreshRequest, session: SessionDep, user: CurrentUser
) -> ApiResponse[None]:
    await service.logout(session, user, payload.refresh_token)
    return ok(None)


@router.get("/meta/privacy")
async def privacy_meta() -> ApiResponse[schema.PrivacyMeta]:
    settings = get_settings()
    return ok(
        schema.PrivacyMeta(
            current_version=settings.privacy_version,
            policy_url=settings.privacy_policy_url,
            sensitive_policy_url=settings.sensitive_policy_url,
        )
    )
