"""档案聚合：overview 一次性取数与 trend 趋势点。

问诊数据用打桩平台生成，聚合本身是纯查询，不需要数据库夹具之外的准备。
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.core.config import get_settings
from app.episode import platform


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


def _draft_ready(triage: str, department: str) -> dict[str, Any]:
    return {
        "status": "draft_ready",
        # v2：normalized 是理解输出，档案趋势的关键词统计从它取值
        "normalized": {"symptom": "流涕咳嗽三天了"},
        "self_attribution": [],
        "draft": {
            "triage": triage,
            "department_primary": department,
            "department_secondary": None,
            "conditions": [],
        },
        "output_list": [],
    }


@pytest.fixture
def user(db_client: TestClient) -> dict[str, Any]:
    data = _register(db_client, "13800000001")
    response = db_client.put(
        "/api/profile",
        json={"birth_date": "1990-06-12", "sex": "male"},
        headers=_auth(data),
    )
    assert response.status_code == 200
    return data


def _post_vital(db_client: TestClient, data: dict[str, Any], **fields: object) -> None:
    response = db_client.post("/api/vitals", json=fields, headers=_auth(data))
    assert response.status_code == 200, response.text


def test_overview_collects_everything(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_call(request: dict[str, Any], session_id: str) -> dict[str, Any]:
        return _draft_ready("clinic", "呼吸内科")

    monkeypatch.setattr(platform, "call_triage", fake_call)
    _post_vital(
        db_client, user, kind="height", measured_at="2026-11-20 08:00:00+08:00", height_cm=170
    )
    _post_vital(
        db_client, user, kind="weight", measured_at="2026-11-20 08:05:00+08:00", weight_kg=70.5
    )
    _post_vital(
        db_client,
        user,
        kind="bp",
        measured_at="2026-11-20 08:10:00+08:00",
        systolic=128,
        diastolic=82,
        pulse=72,
    )

    headers = {**_auth(user), "Idempotency-Key": "1f2e3d4c-5b6a-4978-8a79-0123456789ab"}
    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流涕三天了"}, headers=headers
    ) as stream:
        stream.read()

    response = db_client.get("/api/archive/overview", headers=_auth(user))
    data = _body(response)["data"]

    assert data["profile"]["sex"] == "male"
    vitals = data["vitals"]
    assert vitals["latest_height_cm"] == 170.0
    assert vitals["latest_weight_kg"] == 70.5
    assert vitals["bmi"] == 24.4  # 70.5 / 1.70^2，保留 1 位
    assert vitals["latest_bp"]["systolic"] == 128
    assert data["trend_summary"]["episodes_90d"] == 1
    assert data["trend_summary"]["latest_triage"] == "clinic"
    assert data["pending"]["recheck"] == 1  # clinic 档位保存建了复查提醒
    assert data["pending"]["total"] == 1


def test_overview_without_any_data(db_client: TestClient) -> None:
    data = _register(db_client, "13800000002")

    response = db_client.get("/api/archive/overview", headers=_auth(data))
    body = _body(response)["data"]

    assert response.status_code == 200
    assert body["profile"] is None
    assert body["vitals"]["bmi"] is None
    assert body["vitals"]["latest_bp"] is None
    assert body["trend_summary"]["episodes_90d"] == 0
    assert body["trend_summary"]["latest_triage"] is None
    assert body["pending"]["total"] == 0


def test_trend_points_and_keywords(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_call(request: dict[str, Any], session_id: str) -> dict[str, Any]:
        return _draft_ready("clinic", "呼吸内科")

    monkeypatch.setattr(platform, "call_triage", fake_call)
    _post_vital(
        db_client, user, kind="weight", measured_at="2026-11-20 08:00:00+08:00", weight_kg=70.0
    )
    _post_vital(
        db_client, user, kind="weight", measured_at="2026-11-20 18:00:00+08:00", weight_kg=71.0
    )  # 同日第二次测量，取最后一次
    _post_vital(
        db_client,
        user,
        kind="bp",
        measured_at="2026-11-20 08:10:00+08:00",
        systolic=120,
        diastolic=80,
    )

    headers = {**_auth(user), "Idempotency-Key": "1f2e3d4c-5b6a-4978-8a79-0123456789ab"}
    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流涕咳嗽三天了"}, headers=headers
    ) as stream:
        stream.read()

    response = db_client.get("/api/archive/trend?days=90&limit=10", headers=_auth(user))
    data = _body(response)["data"]

    assert len(data["weight_points"]) == 1
    assert data["weight_points"][0]["weight_kg"] == 71.0  # 同日取最后一次
    assert data["bp_points"][0]["systolic"] == 120
    assert data["triage_points"][0]["triage"] == "clinic"
    keywords = {item["term"]: item["count"] for item in data["symptom_keywords"]}
    # 折算文本 "流涕咳嗽三天了" 命中归一化映射表的临床词面「流涕」
    assert keywords.get("流涕") == 1


def test_trend_validates_params(db_client: TestClient, user: dict[str, Any]) -> None:
    assert db_client.get("/api/archive/trend?days=400", headers=_auth(user)).status_code == 400
    assert db_client.get("/api/archive/trend?limit=99", headers=_auth(user)).status_code == 400


def test_archive_overview_requires_auth(db_client: TestClient) -> None:
    assert db_client.get("/api/archive/overview").status_code == 401
    assert db_client.get("/api/archive/trend").status_code == 401
