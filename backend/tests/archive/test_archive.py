"""档案域测试：体征数值边界、身高单值语义、用药校验与计划联动。"""

from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from app.core.config import get_settings


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


MEASURED = "2026-11-20 08:10:00+08:00"


def _post_vital(client: TestClient, data: dict[str, Any], **fields: object) -> Response:
    response: Response = client.post("/api/vitals", json=fields, headers=_auth(data))
    return response


# ---- 体征 ----


def test_create_and_list_vitals(db_client: TestClient) -> None:
    data = _register(db_client, "13800000001")

    assert (
        _post_vital(
            db_client, data, kind="bp", measured_at=MEASURED, systolic=128, diastolic=82, pulse=72
        ).status_code
        == 200
    )
    assert (
        _post_vital(
            db_client, data, kind="weight", measured_at=MEASURED, weight_kg=70.5
        ).status_code
        == 200
    )

    response = db_client.get("/api/vitals", headers=_auth(data))
    page = _body(response)["data"]
    assert page["total"] == 2
    kinds = {record["kind"] for record in page["records"]}
    assert kinds == {"bp", "weight"}

    bp_only = db_client.get("/api/vitals?kind=bp", headers=_auth(data))
    assert _body(bp_only)["data"]["total"] == 1


def test_vital_ranges_enforced(db_client: TestClient) -> None:
    data = _register(db_client, "13800000002")

    out_of_range = _post_vital(
        db_client, data, kind="bp", measured_at=MEASURED, systolic=300, diastolic=82
    )
    assert out_of_range.status_code == 400
    assert _body(out_of_range)["code"] == 3002

    missing = _post_vital(db_client, data, kind="weight", measured_at=MEASURED)
    assert missing.status_code == 400
    assert _body(missing)["code"] == 3002

    bad_kind = _post_vital(db_client, data, kind="spo2", measured_at=MEASURED)
    assert bad_kind.status_code == 400


def test_height_is_single_valued(db_client: TestClient) -> None:
    data = _register(db_client, "13800000003")

    _post_vital(db_client, data, kind="height", measured_at=MEASURED, height_cm=170)
    _post_vital(
        db_client, data, kind="height", measured_at="2026-11-21 08:00:00+08:00", height_cm=175
    )

    response = db_client.get("/api/vitals?kind=height", headers=_auth(data))
    page = _body(response)["data"]
    assert page["total"] == 1
    assert page["records"][0]["height_cm"] == 175.0


def test_vital_update_and_delete(db_client: TestClient) -> None:
    data = _register(db_client, "13800000004")
    created = _body(
        _post_vital(db_client, data, kind="bp", measured_at=MEASURED, systolic=128, diastolic=82)
    )["data"]
    vital_id = created["id"]

    updated = db_client.put(
        f"/api/vitals/{vital_id}",
        json={"systolic": 120},
        headers=_auth(data),
    )
    assert _body(updated)["data"]["systolic"] == 120
    assert _body(updated)["data"]["diastolic"] == 82

    deleted = db_client.delete(f"/api/vitals/{vital_id}", headers=_auth(data))
    assert deleted.status_code == 200

    missing = db_client.get("/api/vitals", headers=_auth(data))
    assert _body(missing)["data"]["total"] == 0


def test_vital_ownership_is_enforced(db_client: TestClient) -> None:
    owner = _register(db_client, "13800000005")
    other = _register(db_client, "13800000006")
    vital_id = _body(
        _post_vital(db_client, owner, kind="weight", measured_at=MEASURED, weight_kg=70)
    )["data"]["id"]

    response = db_client.delete(f"/api/vitals/{vital_id}", headers=_auth(other))

    assert response.status_code == 404


# ---- 用药 ----


def test_medication_crud_and_validation(db_client: TestClient) -> None:
    data = _register(db_client, "13800000007")

    created = db_client.post(
        "/api/medications",
        json={
            "name": "氨氯地平",
            "dosage_text": "1 片",
            "frequency_text": "一天一次",
            "kind": "long_term",
            "started_on": "2025-03-01",
        },
        headers=_auth(data),
    )
    assert created.status_code == 200

    short_without_end = db_client.post(
        "/api/medications",
        json={"name": "阿莫西林", "kind": "short_term", "started_on": "2026-11-01"},
        headers=_auth(data),
    )
    assert short_without_end.status_code == 400
    assert _body(short_without_end)["code"] == 3003

    end_before_start = db_client.post(
        "/api/medications",
        json={
            "name": "阿莫西林",
            "kind": "short_term",
            "started_on": "2026-11-05",
            "ended_on": "2026-11-01",
        },
        headers=_auth(data),
    )
    assert end_before_start.status_code == 400

    listing = db_client.get("/api/medications?kind=long_term", headers=_auth(data))
    assert _body(listing)["data"]["records"][0]["name"] == "氨氯地平"

    bad_status = db_client.put("/api/medications/1", json={"status": "flying"}, headers=_auth(data))
    assert bad_status.status_code == 400


def test_stopping_medication_stops_plans(db_client: TestClient) -> None:
    data = _register(db_client, "13800000008")
    db_client.post(
        "/api/medications",
        json={"name": "氨氯地平", "kind": "long_term", "started_on": "2025-03-01"},
        headers=_auth(data),
    )
    plan = db_client.post(
        "/api/medication-plans",
        json={"medication_id": 1, "times": ["08:00", "20:00"], "started_on": "2026-11-20"},
        headers=_auth(data),
    )
    assert plan.status_code == 200
    assert _body(plan)["data"]["ended_on"] == "2026-12-20"  # 缺省 +30 天
    assert _body(plan)["data"]["times"] == ["08:00", "20:00"]  # 升序返回

    stopped = db_client.put("/api/medications/1", json={"status": "stopped"}, headers=_auth(data))
    assert stopped.status_code == 200

    plans = db_client.get("/api/medication-plans", headers=_auth(data))
    assert _body(plans)["data"]["records"][0]["status"] == "stopped"


def test_plan_validation(db_client: TestClient) -> None:
    data = _register(db_client, "13800000009")
    db_client.post(
        "/api/medications",
        json={"name": "氯雷他定", "kind": "long_term", "started_on": "2026-11-01"},
        headers=_auth(data),
    )

    bad_time = db_client.post(
        "/api/medication-plans",
        json={"medication_id": 1, "times": ["25:00"], "started_on": "2026-11-20"},
        headers=_auth(data),
    )
    assert bad_time.status_code == 400
    assert _body(bad_time)["code"] == 3003

    duplicated = db_client.post(
        "/api/medication-plans",
        json={"medication_id": 1, "times": ["08:00", "08:00"], "started_on": "2026-11-20"},
        headers=_auth(data),
    )
    assert duplicated.status_code == 400

    other = _register(db_client, "13800000010")
    foreign_med = db_client.post(
        "/api/medication-plans",
        json={"medication_id": 1, "times": ["08:00"], "started_on": "2026-11-20"},
        headers=_auth(other),
    )
    assert foreign_med.status_code == 404


def test_delete_medication_cascades_plans(db_client: TestClient) -> None:
    data = _register(db_client, "13800000011")
    db_client.post(
        "/api/medications",
        json={"name": "氯雷他定", "kind": "long_term", "started_on": "2026-11-01"},
        headers=_auth(data),
    )
    db_client.post(
        "/api/medication-plans",
        json={"medication_id": 1, "times": ["08:00"], "started_on": "2026-11-20"},
        headers=_auth(data),
    )

    response = db_client.delete("/api/medications/1", headers=_auth(data))
    assert response.status_code == 200

    plans = db_client.get("/api/medication-plans", headers=_auth(data))
    assert _body(plans)["data"]["records"] == []
    meds = db_client.get("/api/medications", headers=_auth(data))
    assert _body(meds)["data"]["records"] == []


def test_archive_endpoints_require_auth(db_client: TestClient) -> None:
    assert db_client.get("/api/vitals").status_code == 401
    assert db_client.post("/api/medications", json={}).status_code == 401
    assert db_client.get("/api/medication-plans").status_code == 401
