"""认证接口的行为：注册、登录、刷新轮换、登出与令牌解析。

全部使用合成账号数据。每个用例先清空账号三张表，互不影响。
"""

import re
from datetime import datetime, timedelta
from typing import Any

import jwt
from fastapi.testclient import TestClient
from httpx import Response

from app.common.clock import SHANGHAI
from app.core.config import get_settings

_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def _body(response: Response) -> dict[str, Any]:
    payload: dict[str, Any] = response.json()
    return payload


def _data(response: Response) -> dict[str, Any]:
    data: dict[str, Any] = _body(response)["data"]
    return data


def _register_payload(phone: str) -> dict[str, object]:
    return {
        "phone": phone,
        "password": "passw0rd",
        "consent_version": get_settings().privacy_version,
        "accept_privacy": True,
        "accept_sensitive": True,
    }


def _register(client: TestClient, phone: str = "13800000001") -> dict[str, Any]:
    response = client.post("/api/auth/register", json=_register_payload(phone))
    assert response.status_code == 200, response.text
    return _data(response)


def test_register_returns_user_tokens_and_consent(db_client: TestClient) -> None:
    data = _register(db_client)

    assert data["user"]["phone"] == "13800000001"
    assert data["user"]["is_demo"] is False
    assert data["user"]["created_at"] and _FORMAT.match(data["user"]["created_at"])
    tokens = data["tokens"]
    assert tokens["token_type"] == "Bearer"
    assert tokens["access_token"] and tokens["refresh_token"]
    assert _FORMAT.match(tokens["access_expires_at"])
    assert _FORMAT.match(tokens["refresh_expires_at"])
    assert data["profile_complete"] is False


def test_register_rejects_bad_phone_format(db_client: TestClient) -> None:
    payload = _register_payload("1381234")
    response = db_client.post("/api/auth/register", json=payload)

    assert response.status_code == 400
    assert _body(response)["code"] == 1001


def test_register_rejects_weak_password(db_client: TestClient) -> None:
    payload = _register_payload("13800000002")
    payload["password"] = "abcdefgh"  # 无数字
    response = db_client.post("/api/auth/register", json=payload)

    assert response.status_code == 400
    assert _body(response)["code"] == 1001


def test_register_rejects_without_consent(db_client: TestClient) -> None:
    payload = _register_payload("13800000003")
    payload["accept_sensitive"] = False
    response = db_client.post("/api/auth/register", json=payload)

    assert response.status_code == 403
    assert _body(response)["code"] == 1006


def test_register_rejects_stale_consent_version(db_client: TestClient) -> None:
    payload = _register_payload("13800000004")
    payload["consent_version"] = "2000-01-01"
    response = db_client.post("/api/auth/register", json=payload)

    assert response.status_code == 403
    assert _body(response)["code"] == 1006


def test_register_rejects_duplicate_phone(db_client: TestClient) -> None:
    _register(db_client, "13800000005")

    response = db_client.post("/api/auth/register", json=_register_payload("13800000005"))

    assert response.status_code == 409
    assert _body(response)["code"] == 1002


def test_login_returns_tokens(db_client: TestClient) -> None:
    _register(db_client, "13800000006")

    response = db_client.post(
        "/api/auth/login", json={"phone": "13800000006", "password": "passw0rd"}
    )

    assert response.status_code == 200
    assert _body(response)["data"]["tokens"]["access_token"]


def test_login_rejects_wrong_password(db_client: TestClient) -> None:
    _register(db_client, "13800000007")

    response = db_client.post(
        "/api/auth/login", json={"phone": "13800000007", "password": "wrong1234"}
    )

    assert response.status_code == 401
    assert _body(response)["code"] == 1003


def test_login_locks_after_five_failures(db_client: TestClient) -> None:
    _register(db_client, "13800000008")
    for _ in range(5):
        db_client.post("/api/auth/login", json={"phone": "13800000008", "password": "wrong1234"})

    response = db_client.post(
        "/api/auth/login", json={"phone": "13800000008", "password": "passw0rd"}
    )

    assert response.status_code == 429
    assert _body(response)["code"] == 1008


def test_refresh_rotates_and_replays_fail(db_client: TestClient) -> None:
    data = _register(db_client, "13800000009")
    old_refresh = data["tokens"]["refresh_token"]

    response = db_client.post("/api/auth/refresh", json={"refresh_token": old_refresh})

    assert response.status_code == 200
    new_refresh = _body(response)["data"]["tokens"]["refresh_token"]
    assert new_refresh != old_refresh

    replay = db_client.post("/api/auth/refresh", json={"refresh_token": old_refresh})

    assert replay.status_code == 401
    assert _body(replay)["code"] == 1005


def test_logout_revokes_refresh_token(db_client: TestClient) -> None:
    data = _register(db_client, "13800000010")
    refresh = data["tokens"]["refresh_token"]
    access = data["tokens"]["access_token"]

    response = db_client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 200
    assert _body(response)["data"] is None

    after = db_client.post("/api/auth/refresh", json={"refresh_token": refresh})

    assert after.status_code == 401
    assert _body(after)["code"] == 1005


def test_logout_requires_auth(db_client: TestClient) -> None:
    response = db_client.post("/api/auth/logout", json={"refresh_token": "whatever"})

    assert response.status_code == 401
    assert _body(response)["code"] == 401


def test_expired_access_token_reports_1004(db_client: TestClient) -> None:
    expired = jwt.encode(
        {"sub": "1", "type": "access", "exp": datetime.now(SHANGHAI) - timedelta(minutes=1)},
        get_settings().jwt_secret,
        algorithm="HS256",
    )

    response = db_client.post(
        "/api/auth/logout",
        json={"refresh_token": "whatever"},
        headers={"Authorization": f"Bearer {expired}"},
    )

    assert response.status_code == 401
    assert _body(response)["code"] == 1004


def test_meta_privacy_is_public(db_client: TestClient) -> None:
    response = db_client.get("/api/meta/privacy")

    assert response.status_code == 200
    data = _data(response)
    assert data["current_version"] == get_settings().privacy_version
    # 按配置原样返回有效链接或空串，不能补占位假地址
    assert data["policy_url"] == get_settings().privacy_policy_url
    assert data["sensitive_policy_url"] == get_settings().sensitive_policy_url
