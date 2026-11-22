"""异常类型与全局处理器。异常转成统一响应体，HTTP 状态码跟着错误码走。"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.api import error
from app.common.codes import ErrorCode


class BizException(Exception):
    """业务层主动抛出的错误，由全局处理器转成统一响应体。

    http_status 仅在同一个错误码对应两种状态时覆盖（如 3004 既有 404 也有 409），
    其余场景一律走错误码自己的映射表，不允许随手改状态码。
    """

    def __init__(
        self, code: ErrorCode, message: str | None = None, *, http_status: int | None = None
    ) -> None:
        self.code = code
        self.message = message or code.message
        self.http_status = http_status if http_status is not None else code.http_status
        super().__init__(self.message)


def _envelope(code: ErrorCode, message: str) -> JSONResponse:
    body: dict[str, Any] = error(code, message).model_dump()
    return JSONResponse(status_code=code.http_status, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizException)
    async def handle_biz(_: Request, exc: BizException) -> JSONResponse:
        payload: dict[str, Any] = error(exc.code, exc.message).model_dump()
        return JSONResponse(status_code=exc.http_status, content=payload)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # 参数形状不对属于客户端错误，不能掉进兜底的 500
        errors = exc.errors()
        detail = f"{errors[0]['loc']}: {errors[0]['msg']}" if errors else "参数不合法"
        return _envelope(ErrorCode.INVALID_PARAM, detail)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # 未匹配的路径、不支持的方法都走这里，避免被当成服务端异常
        try:
            code = ErrorCode(exc.status_code)
        except ValueError:
            code = ErrorCode.INTERNAL_ERROR
        return _envelope(code, code.message)

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        return _envelope(ErrorCode.INTERNAL_ERROR, ErrorCode.INTERNAL_ERROR.message)
