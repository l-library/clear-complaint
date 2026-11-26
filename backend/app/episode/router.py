"""问诊路由。流式端点把服务层的事件源逐帧转成 SSE。

流建立前的鉴权与参数错误走普通 JSON 信封（全局处理器兜着），
流内错误折成 error 事件；SSE 头照 docs/api.md 5.11 设置。
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.account import service as account_service
from app.account.models import User
from app.common.api import ApiResponse, ok
from app.db.session import get_session
from app.episode import schema, service
from app.episode.models import Episode

router = APIRouter(tags=["episode"])

CurrentUser = Annotated[User, Depends(account_service.get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
KeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse(event_id: int, name: str, payload: dict[str, object]) -> str:
    body = json.dumps(payload, ensure_ascii=False)
    return f"id: {event_id}\nevent: {name}\ndata: {body}\n\n"


def _stream(source: AsyncIterator[tuple[str, dict[str, object]]]) -> StreamingResponse:
    async def generate() -> AsyncIterator[str]:
        counter = 1
        async for name, payload in source:
            yield _sse(counter, name, payload)
            counter += 1

    return StreamingResponse(generate(), media_type="text/event-stream", headers=SSE_HEADERS)


def _episode_stream(session: AsyncSession, outcome: tuple[Episode, bool]) -> StreamingResponse:
    episode, fresh = outcome
    return _stream(service.episode_events(session, episode, fresh))


@router.post("/episodes")
async def create_episode(
    payload: schema.CreateEpisodeRequest,
    session: SessionDep,
    user: CurrentUser,
    idempotency_key: KeyHeader,
) -> StreamingResponse:
    key = service.parse_idempotency_key(idempotency_key)
    episode, fresh = await service.create_episode(
        session, user.id, payload.complaint, payload.city_code, key
    )
    return _episode_stream(session, (episode, fresh))


@router.post("/episodes/{episode_id}/clarify")
async def answer_episode(
    episode_id: int,
    payload: schema.AnswerRequest,
    session: SessionDep,
    user: CurrentUser,
    idempotency_key: KeyHeader,
) -> StreamingResponse:
    key = service.parse_idempotency_key(idempotency_key)
    episode, fresh = await service.submit_answer(
        session,
        user.id,
        episode_id,
        {
            "question_id": payload.question_id,
            "action": payload.action,
            "text": payload.text,
        },
        key,
    )
    return _episode_stream(session, (episode, fresh))


@router.post("/episodes/{episode_id}/skip-clarify")
async def skip_episode_clarify(
    episode_id: int,
    session: SessionDep,
    user: CurrentUser,
    idempotency_key: KeyHeader,
) -> StreamingResponse:
    key = service.parse_idempotency_key(idempotency_key)
    episode, fresh = await service.skip_clarify(session, user.id, episode_id, key)
    return _episode_stream(session, (episode, fresh))


@router.post("/episodes/{episode_id}/retry")
async def retry_episode(
    episode_id: int,
    session: SessionDep,
    user: CurrentUser,
    idempotency_key: KeyHeader,
) -> StreamingResponse:
    key = service.parse_idempotency_key(idempotency_key)
    episode, fresh = await service.retry_episode(session, user.id, episode_id, key)
    return _episode_stream(session, (episode, fresh))


@router.get("/episodes")
async def list_episodes(
    session: SessionDep,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[str | None, Query()] = None,
    triage: Annotated[str | None, Query()] = None,
) -> ApiResponse[schema.PageData]:
    statuses = [item.strip() for item in (status or "").split(",") if item.strip()]
    triages = [item.strip() for item in (triage or "").split(",") if item.strip()]
    data = await service.list_episodes(session, user.id, page, size, statuses, triages)
    return ok(schema.PageData(**data))


@router.get("/episodes/{episode_id}")
async def episode_detail(
    episode_id: int, session: SessionDep, user: CurrentUser
) -> ApiResponse[schema.EpisodeDetail]:
    detail = await service.episode_detail(session, user.id, episode_id)
    return ok(schema.EpisodeDetail(**detail))


@router.delete("/episodes/{episode_id}")
async def delete_episode(
    episode_id: int, session: SessionDep, user: CurrentUser
) -> ApiResponse[None]:
    await service.delete_episode(session, user.id, episode_id)
    return ok(None)
