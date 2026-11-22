"""对外暴露的路由汇总。挂载前缀只在 main.py 出现一次，各模块里不写 /api。"""

from fastapi import APIRouter

from app.account import router as account_router
from app.archive import router as archive_router
from app.common import web
from app.episode import router as episode_router
from app.reminder import router as reminder_router

api_router = APIRouter()
api_router.include_router(web.router)
api_router.include_router(account_router.router)
api_router.include_router(episode_router.router)
api_router.include_router(archive_router.router)
api_router.include_router(reminder_router.router)
