"""业务错误码。

约定：HTTP 状态码仍然表达语义，响应体里的 code 是业务错误码。
目前两者同值，出现与 HTTP 语义不同的业务错误时再另起号段。
"""

from enum import IntEnum


class ErrorCode(IntEnum):
    INVALID_PARAM = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    INTERNAL_ERROR = 500

    @property
    def message(self) -> str:
        return _MESSAGES[self]

    @property
    def http_status(self) -> int:
        return int(self) if 400 <= int(self) < 600 else 500


_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_PARAM: "参数不合法",
    ErrorCode.UNAUTHORIZED: "未认证",
    ErrorCode.FORBIDDEN: "无权限",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.INTERNAL_ERROR: "服务异常",
}
