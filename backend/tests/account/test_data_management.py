"""数据管理：导出打包、一次性下载、数据清空与账号注销。"""

import io
import json
import zipfile
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.core.config import get_settings
from app.episode import platform as episode_platform


def _body(response: Response) -> dict[str, Any]:
    payload: dict[str, Any] = response.json()
    return payload


def _register(client: TestClient, phone: str) -> dict[str, Any]:
    payload = {
        "phone": phone,
        "password": "passw0rd",
        "consent_version": get_settings().privacy_version,
        "accept_privacy": True,
        "accept_sensitive": True,
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = _body(response)["data"]
    return data


def _auth(data: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {data['tokens']['access_token']}"}


@pytest.fixture
def export_dir(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    directory = tmp_path / "exports"
    monkeypatch.setattr(get_settings(), "export_dir", str(directory))
    return directory


def _seed_profile_and_vitals(db_client: TestClient, data: dict[str, Any]) -> None:
    response = db_client.put(
        "/api/profile",
        json={"birth_date": "1990-06-12", "sex": "female", "name": "张三"},
        headers=_auth(data),
    )
    assert response.status_code == 200
    response = db_client.post(
        "/api/vitals",
        json={"kind": "weight", "measured_at": "2026-11-20 08:00:00+08:00", "weight_kg": 70},
        headers=_auth(data),
    )
    assert response.status_code == 200


def _seed_episode(
    db_client: TestClient, data: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_call(request: dict[str, Any], session_id: str) -> dict[str, Any]:
        return {
            "status": "draft_ready",
            "draft": {
                "triage": "clinic",
                "department_primary": "呼吸内科",
                "department_secondary": None,
                "conditions": [],
            },
            "output_list": [],
        }

    monkeypatch.setattr(episode_platform, "call_triage", fake_call)
    headers = {
        **_auth(data),
        "Idempotency-Key": "1f2e3d4c-5b6a-4978-8a79-0123456789ab",
    }
    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流涕三天了"}, headers=headers
    ) as stream:
        stream.read()
    # 生成完成即自动归档（issue #24），无需再调用保存端点


@pytest.fixture
def user(db_client: TestClient) -> dict[str, Any]:
    return _register(db_client, "13800000001")


# ---- 导出 ----


def test_export_builds_and_downloads_once(
    db_client: TestClient,
    export_dir: Any,
    user: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_profile_and_vitals(db_client, user)
    _seed_episode(db_client, user, monkeypatch)

    built = db_client.get("/api/export", headers=_auth(user))
    assert built.status_code == 200, built.text
    data = _body(built)["data"]
    token = data["url"].rsplit("/", 1)[-1]
    assert data["size_bytes"] > 0
    assert (export_dir / f"{token}.zip").exists()

    # 下载不鉴权
    first = db_client.get(f"/api/export/{token}")
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("application/zip")
    archive = zipfile.ZipFile(io.BytesIO(first.content))
    names = set(archive.namelist())
    assert {"data.json", "episodes.csv"} <= names
    payload = json.loads(archive.read("data.json"))
    assert payload["profile"]["name"] == "张三"
    assert len(payload["episodes"]) == 1
    assert payload["episodes"][0]["complaint_text"] == "流涕三天了"
    assert len(payload["vitals"]) == 1
    assert "qa_turns" in payload
    csv_text = archive.read("episodes.csv").decode()
    assert "流涕三天了" in csv_text

    # 一次性：第二次下载 404
    second = db_client.get(f"/api/export/{token}")
    assert second.status_code == 404

    # 未知令牌不泄露存在性
    assert db_client.get("/api/export/not-a-token").status_code == 404


def test_export_requires_auth(db_client: TestClient) -> None:
    assert db_client.get("/api/export").status_code == 401


# ---- 数据清空 ----


def test_clear_data_requires_confirm_text(db_client: TestClient, user: dict[str, Any]) -> None:
    response = db_client.request(
        "DELETE", "/api/data", json={"confirm": "yes"}, headers=_auth(user)
    )

    assert response.status_code == 400
    assert _body(response)["code"] == 3006


def test_clear_data_keeps_account(
    db_client: TestClient,
    export_dir: Any,
    user: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_profile_and_vitals(db_client, user)
    _seed_episode(db_client, user, monkeypatch)
    built = db_client.get("/api/export", headers=_auth(user))
    token = _body(built)["data"]["url"].rsplit("/", 1)[-1]

    response = db_client.request(
        "DELETE", "/api/data", json={"confirm": "删除"}, headers=_auth(user)
    )
    cleared = _body(response)["data"]["cleared"]

    assert cleared["episodes"] == 1
    assert cleared["vitals"] == 1
    assert cleared["medications"] == 0
    assert cleared["reminders"] == 1

    # 数据没了，账号还在、还能登录
    assert db_client.get("/api/episodes/1", headers=_auth(user)).status_code == 404
    assert db_client.get("/api/profile", headers=_auth(user)).status_code == 200
    login = db_client.post("/api/auth/login", json={"phone": "13800000001", "password": "passw0rd"})
    assert login.status_code == 200

    # 未用完的导出令牌也随数据一起作废
    assert db_client.get(f"/api/export/{token}").status_code == 404


# ---- 账号注销 ----


def test_delete_account_kills_everything(
    db_client: TestClient, export_dir: Any, user: dict[str, Any]
) -> None:
    refresh = user["tokens"]["refresh_token"]

    response = db_client.request(
        "DELETE", "/api/account", json={"confirm": "删除"}, headers=_auth(user)
    )
    assert response.status_code == 200
    assert _body(response)["data"] is None

    # 旧访问令牌与刷新令牌全部失效
    assert db_client.get("/api/profile", headers=_auth(user)).status_code == 401
    refreshed = db_client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert refreshed.status_code == 401
    assert _body(refreshed)["code"] == 1005

    # 账号已不存在
    login = db_client.post("/api/auth/login", json={"phone": "13800000001", "password": "passw0rd"})
    assert login.status_code == 401
