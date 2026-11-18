"""对外暴露的路由汇总。挂载前缀只在 main.py 出现一次，各模块里不写 /api。"""

from fastapi import APIRouter

from app.common import web

api_router = APIRouter()
api_router.include_router(web.router)
