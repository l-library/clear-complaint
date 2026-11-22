"""业务错误码。

三段式：三位数通用段（值与 HTTP 状态码同值，只给框架兜底用），四位数业务段
（1000 账号、2000 问诊、3000 档案与数据、4000 平台），号段定义在 docs/api.md 第 12 节。

四位数业务码的 HTTP 状态码与值不同（如 1008 是 429），所以 http_status 是显式映射表，
不是"值即状态码"。新增码必须同时补 _MESSAGES 与 _HTTP_STATUS，tests/test_codes.py
会检查三张表覆盖一致。
"""

from enum import IntEnum


class ErrorCode(IntEnum):
    # 通用段：值即 HTTP 状态码，供全局处理器把框架异常折成统一响应体
    INVALID_PARAM = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    RATE_LIMITED = 429
    INTERNAL_ERROR = 500

    # 账号段
    PHONE_OR_PASSWORD_INVALID = 1001
    PHONE_ALREADY_REGISTERED = 1002
    LOGIN_CREDENTIALS_WRONG = 1003
    ACCESS_TOKEN_EXPIRED = 1004
    REFRESH_TOKEN_INVALID = 1005
    PRIVACY_CONSENT_REQUIRED = 1006
    ACCOUNT_DISABLED_OR_READONLY = 1007
    LOGIN_TOO_MANY_ATTEMPTS = 1008

    # 问诊段
    COMPLAINT_EMPTY = 2001
    COMPLAINT_TOO_LONG = 2002
    CLARIFY_ROUNDS_EXHAUSTED = 2003
    EPISODE_NOT_FOUND = 2004
    EPISODE_STATE_NOT_ALLOWED = 2005
    IDEMPOTENCY_KEY_CONFLICT = 2006
    CLARIFY_FIELD_INVALID = 2007
    QA_TURNS_EXHAUSTED = 2008

    # 档案与数据段
    PROFILE_REQUIRED_MISSING = 3001
    VITAL_OUT_OF_RANGE = 3002
    MEDICATION_INVALID = 3003
    REMINDER_NOT_FOUND_OR_DONE = 3004
    EXPORT_TOO_LARGE = 3005
    DELETE_CONFIRM_MISMATCH = 3006

    # 平台段（AgentArts 调用）
    AGENTARTS_UNAVAILABLE = 4001
    AGENTARTS_TIMEOUT = 4002
    AGENTARTS_THROTTLED = 4003
    AGENTARTS_DRAFT_INVALID = 4004

    @property
    def message(self) -> str:
        return _MESSAGES[self]

    @property
    def http_status(self) -> int:
        return _HTTP_STATUS[self]


_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_PARAM: "参数不合法",
    ErrorCode.UNAUTHORIZED: "未认证",
    ErrorCode.FORBIDDEN: "无权限",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.METHOD_NOT_ALLOWED: "方法不被允许",
    ErrorCode.CONFLICT: "状态冲突",
    ErrorCode.RATE_LIMITED: "请求过于频繁",
    ErrorCode.INTERNAL_ERROR: "服务异常",
    ErrorCode.PHONE_OR_PASSWORD_INVALID: "手机号或密码格式不合规",
    ErrorCode.PHONE_ALREADY_REGISTERED: "手机号已注册",
    ErrorCode.LOGIN_CREDENTIALS_WRONG: "账号或密码错误",
    ErrorCode.ACCESS_TOKEN_EXPIRED: "访问令牌过期",
    ErrorCode.REFRESH_TOKEN_INVALID: "刷新令牌无效或已被使用",
    ErrorCode.PRIVACY_CONSENT_REQUIRED: "未同意隐私政策或同意版本过期",
    ErrorCode.ACCOUNT_DISABLED_OR_READONLY: "账号停用或演示账号只读",
    ErrorCode.LOGIN_TOO_MANY_ATTEMPTS: "登录尝试过多，请稍后再试",
    ErrorCode.COMPLAINT_EMPTY: "主诉为空",
    ErrorCode.COMPLAINT_TOO_LONG: "主诉超长",
    ErrorCode.CLARIFY_ROUNDS_EXHAUSTED: "追问轮次已达上限",
    ErrorCode.EPISODE_NOT_FOUND: "问诊不存在或已过期",
    ErrorCode.EPISODE_STATE_NOT_ALLOWED: "问诊状态不允许该操作",
    ErrorCode.IDEMPOTENCY_KEY_CONFLICT: "幂等键冲突",
    ErrorCode.CLARIFY_FIELD_INVALID: "追问答案字段不合法",
    ErrorCode.QA_TURNS_EXHAUSTED: "该问诊的问答次数已达上限",
    ErrorCode.PROFILE_REQUIRED_MISSING: "档案必填项缺失",
    ErrorCode.VITAL_OUT_OF_RANGE: "体征数值超出范围",
    ErrorCode.MEDICATION_INVALID: "用药记录或计划不合法",
    ErrorCode.REMINDER_NOT_FOUND_OR_DONE: "提醒不存在或已处理",
    ErrorCode.EXPORT_TOO_LARGE: "导出数据过大",
    ErrorCode.DELETE_CONFIRM_MISMATCH: "删除确认不匹配",
    ErrorCode.AGENTARTS_UNAVAILABLE: "平台不可用",
    ErrorCode.AGENTARTS_TIMEOUT: "平台超时",
    ErrorCode.AGENTARTS_THROTTLED: "平台限流或额度不足",
    ErrorCode.AGENTARTS_DRAFT_INVALID: "草稿结构不合规",
}

# 3004 默认 404（不存在）；"已处理"的场景由抛出方用 http_status=409 覆盖
_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_PARAM: 400,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.CONFLICT: 409,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.PHONE_OR_PASSWORD_INVALID: 400,
    ErrorCode.PHONE_ALREADY_REGISTERED: 409,
    ErrorCode.LOGIN_CREDENTIALS_WRONG: 401,
    ErrorCode.ACCESS_TOKEN_EXPIRED: 401,
    ErrorCode.REFRESH_TOKEN_INVALID: 401,
    ErrorCode.PRIVACY_CONSENT_REQUIRED: 403,
    ErrorCode.ACCOUNT_DISABLED_OR_READONLY: 403,
    ErrorCode.LOGIN_TOO_MANY_ATTEMPTS: 429,
    ErrorCode.COMPLAINT_EMPTY: 400,
    ErrorCode.COMPLAINT_TOO_LONG: 400,
    ErrorCode.CLARIFY_ROUNDS_EXHAUSTED: 409,
    ErrorCode.EPISODE_NOT_FOUND: 404,
    ErrorCode.EPISODE_STATE_NOT_ALLOWED: 409,
    ErrorCode.IDEMPOTENCY_KEY_CONFLICT: 409,
    ErrorCode.CLARIFY_FIELD_INVALID: 400,
    ErrorCode.QA_TURNS_EXHAUSTED: 409,
    ErrorCode.PROFILE_REQUIRED_MISSING: 409,
    ErrorCode.VITAL_OUT_OF_RANGE: 400,
    ErrorCode.MEDICATION_INVALID: 400,
    ErrorCode.REMINDER_NOT_FOUND_OR_DONE: 404,
    ErrorCode.EXPORT_TOO_LARGE: 413,
    ErrorCode.DELETE_CONFIRM_MISMATCH: 400,
    ErrorCode.AGENTARTS_UNAVAILABLE: 502,
    ErrorCode.AGENTARTS_TIMEOUT: 504,
    ErrorCode.AGENTARTS_THROTTLED: 503,
    ErrorCode.AGENTARTS_DRAFT_INVALID: 502,
}
