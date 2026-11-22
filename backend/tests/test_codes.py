"""错误码三张表（枚举、文案、HTTP 映射）的一致性与全局处理器的行为。

号段和状态码的依据是 docs/api.md 第 12 节，改号段先改文档再改这里。
"""

import pytest
from fastapi.testclient import TestClient

from app.common.codes import _HTTP_STATUS, _MESSAGES, ErrorCode
from app.common.errors import BizException
from app.main import app


def test_every_code_has_message_and_http_status() -> None:
    assert set(_MESSAGES) == set(ErrorCode)
    assert set(_HTTP_STATUS) == set(ErrorCode)
    for code in ErrorCode:
        assert 400 <= _HTTP_STATUS[code] < 600
        assert _MESSAGES[code]


# docs/api.md 12.2 里状态码与业务码不同值的抽样；抽的是最容易写错的那几条
@pytest.mark.parametrize(
    ("code", "status"),
    [
        (ErrorCode.PHONE_ALREADY_REGISTERED, 409),
        (ErrorCode.LOGIN_TOO_MANY_ATTEMPTS, 429),
        (ErrorCode.EPISODE_NOT_FOUND, 404),
        (ErrorCode.EPISODE_STATE_NOT_ALLOWED, 409),
        (ErrorCode.EXPORT_TOO_LARGE, 413),
        (ErrorCode.AGENTARTS_TIMEOUT, 504),
        (ErrorCode.AGENTARTS_THROTTLED, 503),
        (ErrorCode.REMINDER_NOT_FOUND_OR_DONE, 404),
    ],
)
def test_business_codes_carry_their_own_http_status(code: ErrorCode, status: int) -> None:
    assert code.http_status == status


def test_biz_exception_defaults_to_code_http_status() -> None:
    exc = BizException(ErrorCode.EPISODE_NOT_FOUND)
    assert exc.http_status == 404
    assert exc.message == ErrorCode.EPISODE_NOT_FOUND.message


def test_biz_exception_can_override_http_status() -> None:
    # 3004 兼有两种状态：不存在是 404，已处理是 409
    exc = BizException(ErrorCode.REMINDER_NOT_FOUND_OR_DONE, http_status=409)
    assert exc.code == ErrorCode.REMINDER_NOT_FOUND_OR_DONE
    assert exc.http_status == 409


# 只在测试进程里注册，不进业务路由
@app.post("/api/_raise-biz")
async def _raise_biz() -> None:
    raise BizException(ErrorCode.PHONE_ALREADY_REGISTERED)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_biz_exception_becomes_envelope(client: TestClient) -> None:
    response = client.post("/api/_raise-biz")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == 1002
    assert body["message"] == "手机号已注册"
    assert body["data"] is None


def test_unsupported_method_is_405_not_500(client: TestClient) -> None:
    response = client.delete("/api/health")

    assert response.status_code == 405
    assert response.json()["code"] == 405
