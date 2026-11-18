from fastapi import FastAPI

from app.api import api_router
from app.common.errors import register_exception_handlers
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    register_exception_handlers(app)
    # 接口前缀只在这里出现一次，模块里不写 /api
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
