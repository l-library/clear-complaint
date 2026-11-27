"""日报的 HTTP 契约：鉴权、日期规则、同日幂等、status → 信封、信任边界。

平台调用在 app.daily.platform.call_daily 打桩（同 D2 的 service 测试），这里只验
路由层：用户身份从令牌取、请求体里不接受指标或档案字段、落库行按 status 折成信封。
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.common.clock import now_shanghai
from app.core.config import get_settings
from app.daily import mock_watch
from daily.support import (
    WORKFLOW_VERSION,
    RunDb,
    invalid_input_result,
    platform_result,
    stored,
    stub_platform,
    watch_data_with,
)

TODAY = now_shanghai().date()
PAST = TODAY - timedelta(days=3)
TOMORROW = TODAY + timedelta(days=1)


def _body(response: Response) -> dict[str, Any]:
    payload: dict[str, Any] = response.json()
    return payload


def _auth(user: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['tokens']['access_token']}"}


@pytest.fixture
def user(db_client: TestClient) -> dict[str, Any]:
    payload = {
        "phone": "13800000001",
        "password": "passw0rd",
        "consent_version": get_settings().privacy_version,
        "accept_privacy": True,
        "accept_sensitive": True,
    }
    response = db_client.post("/api/auth/register", json=payload)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = _body(response)["data"]
    return data


def _generate(client: TestClient, user: dict[str, Any], **body: object) -> Response:
    response: Response = client.post("/api/daily/generate", json=body, headers=_auth(user))
    return response


def _get(client: TestClient, user: dict[str, Any], day: str) -> Response:
    response: Response = client.get(f"/api/daily?date={day}", headers=_auth(user))
    return response


# ---- 鉴权与信任边界 ----


def test_both_endpoints_require_token(db_client: TestClient) -> None:
    missing = db_client.get("/api/daily")

    assert missing.status_code == 401
    assert _body(missing)["code"] == 401

    assert db_client.post("/api/daily/generate", json={}).status_code == 401


def test_body_with_watch_data_or_archive_is_rejected(
    db_client: TestClient, user: dict[str, Any], run_db: RunDb
) -> None:
    watch = _generate(
        db_client,
        user,
        watch_data={"date": TODAY.isoformat(), "metrics": {"steps": {"value": 4600}}},
    )
    assert watch.status_code == 400
    assert _body(watch)["code"] == 400

    archive = db_client.post(
        "/api/daily/generate",
        json={"health_archive": {"confirmed_conditions": []}},
        headers=_auth(user),
    )
    assert archive.status_code == 400
    assert _body(archive)["code"] == 400

    # 前端提交的指标与档案一个都没落库
    assert stored(run_db, user["user"]["id"]) == []


# ---- 日期规则 ----


def test_future_report_date_is_rejected(
    db_client: TestClient, user: dict[str, Any], run_db: RunDb
) -> None:
    posted = _generate(db_client, user, report_date=TOMORROW.isoformat())

    assert posted.status_code == 400
    assert _body(posted)["code"] == 400

    # GET 走同一条规则：日报只总结已经发生的一天
    assert _get(db_client, user, TOMORROW.isoformat()).status_code == 400
    assert stored(run_db, user["user"]["id"]) == []


def test_malformed_report_date_is_rejected(db_client: TestClient, user: dict[str, Any]) -> None:
    posted = _generate(db_client, user, report_date="20261123")

    assert posted.status_code == 400
    assert _body(posted)["code"] == 400


# ---- 生成 ----


def test_generate_today_returns_ready_report_with_mock_marker(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub_platform(monkeypatch, lambda request: platform_result(request))

    response = _generate(db_client, user)

    assert response.status_code == 200, response.text
    body = _body(response)
    assert body["code"] == 0
    data = body["data"]
    assert data["report_date"] == TODAY.isoformat()
    assert data["status"] == "ready"
    assert data["degraded"] is False
    # 模拟标记全链路保留，前端据此展示「模拟数据演示」
    assert data["data_source"] == "mock"
    assert data["workflow_version"] == WORKFLOW_VERSION
    assert data["summary"] is not None
    assert data["used_record_ids"] == []
    assert data["created_at"] and data["updated_at"]
    # 指标是后端自己拼的，不来自请求体
    assert len(calls) == 1
    assert calls[0]["report_date"] == TODAY.isoformat()
    assert isinstance(calls[0]["watch_data"], dict)


def test_generate_degraded_report_carries_the_flag(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(monkeypatch, lambda request: platform_result(request, status="degraded"))

    response = _generate(db_client, user)

    assert response.status_code == 200, response.text
    data = _body(response)["data"]
    assert data["status"] == "degraded"
    assert data["degraded"] is True


def test_generate_explicit_past_date(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub_platform(monkeypatch, lambda request: platform_result(request))

    response = _generate(db_client, user, report_date=PAST.isoformat())

    assert response.status_code == 200, response.text
    assert _body(response)["data"]["report_date"] == PAST.isoformat()
    assert calls[0]["report_date"] == PAST.isoformat()


def test_generate_twice_same_day_updates_one_row(
    db_client: TestClient, user: dict[str, Any], run_db: RunDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(monkeypatch, lambda request: platform_result(request))

    first = _generate(db_client, user, report_date=PAST.isoformat())
    second = _generate(db_client, user, report_date=PAST.isoformat())

    assert first.status_code == 200 and second.status_code == 200
    rows = stored(run_db, user["user"]["id"])
    assert len(rows) == 1
    assert rows[0]["report_date"] == PAST
    # 覆盖式重算：同一行被更新，created_at 不变而 updated_at 前进
    first_data = _body(first)["data"]
    second_data = _body(second)["data"]
    assert first_data["created_at"] == second_data["created_at"]
    assert second_data["updated_at"] >= first_data["updated_at"]


# ---- status → 信封 ----


def test_review_required_keeps_null_summary_and_returns_its_code(
    db_client: TestClient, user: dict[str, Any], run_db: RunDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    watch = watch_data_with(
        user["user"]["id"], TODAY, fall_detection={"detected": True, "quality": "usable"}
    )
    monkeypatch.setattr(mock_watch, "build_watch_data", lambda *_: watch)

    def boom(_: object) -> dict[str, Any]:
        raise AssertionError("本地已判定 review_required，不应调用平台")

    stub_platform(monkeypatch, boom)

    posted = _generate(db_client, user)

    # 落库的 review_required 行没有正文；接口给业务码而不是 500（序列化容得下 null）
    assert posted.status_code == 409
    assert _body(posted)["code"] == 5003
    rows = stored(run_db, user["user"]["id"])
    assert len(rows) == 1
    assert rows[0]["status"] == "review_required"
    assert rows[0]["summary"] is None

    fetched = _get(db_client, user, TODAY.isoformat())
    assert fetched.status_code == 409
    assert _body(fetched)["code"] == 5003


def test_platform_invalid_input_returns_its_code_and_saves_nothing(
    db_client: TestClient, user: dict[str, Any], run_db: RunDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(monkeypatch, invalid_input_result)

    response = _generate(db_client, user)

    # 16.8.8：被拒的输入不当成正常报告保存
    assert response.status_code == 400
    body = _body(response)
    assert body["code"] == 5004
    assert body["data"] is None
    assert stored(run_db, user["user"]["id"]) == []


def test_data_insufficient_returns_its_own_code(
    db_client: TestClient, user: dict[str, Any], run_db: RunDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(
        monkeypatch,
        lambda request: platform_result(
            request,
            status="data_insufficient",
            data_quality={"available_metric_ids": [], "coverage_limited": False},
        ),
    )

    posted = _generate(db_client, user)

    assert posted.status_code == 409
    assert _body(posted)["code"] == 5002
    rows = stored(run_db, user["user"]["id"])
    assert [row["status"] for row in rows] == ["data_insufficient"]

    assert _body(_get(db_client, user, TODAY.isoformat()))["code"] == 5002


# ---- 读取 ----


def test_get_without_report_returns_the_not_found_code(
    db_client: TestClient, user: dict[str, Any]
) -> None:
    response = _get(db_client, user, PAST.isoformat())

    assert response.status_code == 404
    body = _body(response)
    assert body["code"] == 5001
    assert body["data"] is None


def test_get_returns_the_newest_row_after_a_version_bump(
    db_client: TestClient,
    user: dict[str, Any],
    run_db: RunDb,
    db_execute: Callable[[str], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_platform(monkeypatch, lambda request: platform_result(request))
    older = _generate(db_client, user, report_date=PAST.isoformat())
    assert older.status_code == 200

    newer_version = "2026-11-28.daily-companion.3"
    stub_platform(
        monkeypatch,
        lambda request: platform_result(request, workflow_version=newer_version),
    )
    newer = _generate(db_client, user, report_date=PAST.isoformat())
    assert newer.status_code == 200

    # 平台升版后同日两行；把旧行推回一小时，读侧必须取新行
    db_execute(
        "UPDATE daily_report SET updated_at = updated_at - interval '1 hour'"
        f" WHERE workflow_version = '{WORKFLOW_VERSION}'"
    )

    fetched = _get(db_client, user, PAST.isoformat())

    assert fetched.status_code == 200
    data = _body(fetched)["data"]
    assert data["workflow_version"] == newer_version
    assert len(stored(run_db, user["user"]["id"])) == 2
