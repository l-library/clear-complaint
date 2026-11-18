from pydantic import BaseModel

from app.common.codes import ErrorCode

SUCCESS = 0


class ApiResponse[T](BaseModel):
    """所有业务接口的统一响应体。code 为 0 表示成功，非 0 取 ErrorCode 的值。"""

    code: int
    message: str
    data: T | None = None


def ok[T](data: T | None = None) -> ApiResponse[T]:
    return ApiResponse(code=SUCCESS, message="ok", data=data)


def error(code: ErrorCode, message: str | None = None) -> ApiResponse[None]:
    return ApiResponse(code=int(code), message=message or code.message, data=None)
