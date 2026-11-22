import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.common.errors import register_exception_handlers
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    task: asyncio.Task[None] | None = None
    if get_settings().scheduler_enabled:
        from app.scheduler import run_forever

        task = asyncio.create_task(run_forever())
    yield
    if task is not None:
        task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    # 接口前缀只在这里出现一次，模块里不写 /api
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
