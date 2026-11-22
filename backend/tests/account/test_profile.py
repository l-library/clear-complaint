"""档案接口：部分更新语义、必填项计算、城市成对提交与隐私同意记录。

全部使用合成数据。PUT 语义（docs/api.md 6.3）：未出现的字段保持不变，
出现的字段提交 null/""/[] 视为清空。
"""

import re
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from app.core.config import get_settings

_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


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


def _auth_headers(data: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {data['tokens']['access_token']}"}


def _put_profile(client: TestClient, data: dict[str, Any], **fields: object) -> Response:
    response: Response = client.put("/api/profile", json=fields, headers=_auth_headers(data))
    return response


def test_get_profile_before_init_is_null(db_client: TestClient) -> None:
    data = _register(db_client, "13800000001")

    response = db_client.get("/api/profile", headers=_auth_headers(data))

    assert response.status_code == 200
    assert _body(response)["data"]["profile"] is None


def test_put_profile_creates_and_returns_it(db_client: TestClient) -> None:
    data = _register(db_client, "13800000002")

    response = _put_profile(
        db_client,
        data,
        name="张三",
        birth_date="1990-06-12",
        sex="male",
        city_code="310100",
        city_name="上海市",
        conditions=["高血压"],
        condition_note="2019 年确诊",
    )

    assert response.status_code == 200, response.text
    profile = _body(response)["data"]
    assert profile["name"] == "张三"
    assert profile["birth_date"] == "1990-06-12"
    assert isinstance(profile["age_years"], int)
    assert profile["sex"] == "male"
    assert profile["city_code"] == "310100"
    assert profile["conditions"] == ["高血压"]
    assert profile["required_missing"] == []
    assert _FORMAT.match(profile["updated_at"])


def test_partial_update_keeps_other_fields(db_client: TestClient) -> None:
    data = _register(db_client, "13800000003")
    _put_profile(db_client, data, birth_date="1990-06-12", sex="female")

    response = _put_profile(db_client, data, name="李四")

    assert response.status_code == 200
    profile = _body(response)["data"]
    assert profile["name"] == "李四"
    assert profile["birth_date"] == "1990-06-12"
    assert profile["sex"] == "female"


def test_required_missing_before_required_fields(db_client: TestClient) -> None:
    data = _register(db_client, "13800000004")

    response = _put_profile(db_client, data, name="王五")

    profile = _body(response)["data"]
    assert profile["required_missing"] == ["birth_date", "sex"]


def test_login_reports_profile_complete(db_client: TestClient) -> None:
    data = _register(db_client, "13800000005")

    before = db_client.post(
        "/api/auth/login", json={"phone": "13800000005", "password": "passw0rd"}
    )
    assert _body(before)["data"]["profile_complete"] is False

    _put_profile(db_client, data, birth_date="1990-06-12", sex="male")

    after = db_client.post("/api/auth/login", json={"phone": "13800000005", "password": "passw0rd"})
    assert _body(after)["data"]["profile_complete"] is True


def test_clearing_fields(db_client: TestClient) -> None:
    data = _register(db_client, "13800000006")
    _put_profile(
        db_client,
        data,
        conditions=["高血压"],
        condition_note="2019 年确诊",
        name="赵六",
    )

    response = _put_profile(db_client, data, name="", condition_note="", conditions=[])

    profile = _body(response)["data"]
    # 空数组是"明确确认没有"，落库原样保留语义
    assert profile["conditions"] == []
    assert profile["condition_note"] is None
    assert profile["name"] is None


def test_city_pair_must_arrive_together(db_client: TestClient) -> None:
    data = _register(db_client, "13800000007")

    only_code = _put_profile(db_client, data, city_code="310100")
    assert only_code.status_code == 400
    assert "city" in _body(only_code)["message"]

    ok = _put_profile(db_client, data, city_code="310100", city_name="上海市")
    assert ok.status_code == 200

    cleared = _put_profile(db_client, data, city_code=None, city_name=None)
    assert cleared.status_code == 200
    assert _body(cleared)["data"]["city_code"] is None


def test_birth_date_bounds(db_client: TestClient) -> None:
    data = _register(db_client, "13800000008")

    malformed = _put_profile(db_client, data, birth_date="1990/6/12")
    assert malformed.status_code == 400

    too_old = _put_profile(db_client, data, birth_date="1899-12-31")
    assert too_old.status_code == 400


def test_sex_must_be_enum(db_client: TestClient) -> None:
    data = _register(db_client, "13800000009")

    response = _put_profile(db_client, data, sex="man")

    assert response.status_code == 400
    assert "sex" in _body(response)["message"]


def test_terms_length_limits(db_client: TestClient) -> None:
    data = _register(db_client, "13800000010")

    too_many = _put_profile(db_client, data, conditions=["病"] * 11)
    assert too_many.status_code == 400

    too_long = _put_profile(db_client, data, allergies=["a" * 21])
    assert too_long.status_code == 400

    empty_item = _put_profile(db_client, data, allergies=[""])
    assert empty_item.status_code == 400


def test_privacy_record_after_register(db_client: TestClient) -> None:
    data = _register(db_client, "13800000011")

    response = db_client.get("/api/profile/privacy", headers=_auth_headers(data))

    assert response.status_code == 200
    record = _body(response)["data"]
    assert record["current_version"] == get_settings().privacy_version
    assert record["consented_version"] == get_settings().privacy_version
    assert _FORMAT.match(record["consented_at"])
    assert record["outdated"] is False


def test_profile_endpoints_require_auth(db_client: TestClient) -> None:
    assert db_client.get("/api/profile").status_code == 401
    assert db_client.put("/api/profile", json={"name": "x"}).status_code == 401
    assert db_client.get("/api/profile/privacy").status_code == 401
