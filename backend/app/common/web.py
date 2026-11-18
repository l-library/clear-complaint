"""系统端点：连通性检查与健康检查。前端用它确认代理和统一响应体都对得上。"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.common.api import ApiResponse, ok

router = APIRouter(tags=["system"])


class PingData(BaseModel):
    status: str


class HealthData(BaseModel):
    status: str
    service: str


@router.get("/ping")
async def ping() -> ApiResponse[PingData]:
    return ok(PingData(status="up"))


@router.get("/health")
async def health() -> ApiResponse[HealthData]:
    return ok(HealthData(status="up", service="clear-complaint-backend"))
