"""提醒域测试：按日列表、响应动作、随访八条规则与第二层、定时任务幂等。"""

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.episode import platform as episode_platform
from app.reminder import models as reminder_models
from app.reminder import platform
from app.scheduler import generate_medication_reminders, purge_expired_episodes

if TYPE_CHECKING:
    RunDb = Callable[[Callable[[AsyncSession], Awaitable[object]]], object]


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
        json={"birth_date": "1990-06-12", "sex": "female"},
        headers=_auth(data),
    )
    assert response.status_code == 200
    return data


def _create_episode(
    db_client: TestClient,
    data: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    triage: str,
) -> None:
    async def fake_call(request: dict[str, Any], session_id: str) -> dict[str, Any]:
        return _draft_ready(triage, "呼吸内科")

    monkeypatch.setattr(episode_platform, "call_triage", fake_call)
    headers = {
        **_auth(data),
        "Idempotency-Key": "1f2e3d4c-5b6a-4978-8a79-0123456789ab",
    }
    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流涕三天了"}, headers=headers
    ) as stream:
        stream.read()


def _save_episode(db_client: TestClient, data: dict[str, Any], reminder: bool) -> dict[str, Any]:
    response = db_client.post(
        "/api/episodes/1/save", json={"save": True, "reminder": reminder}, headers=_auth(data)
    )
    assert response.status_code == 200, response.text
    saved: dict[str, Any] = _body(response)["data"]
    return saved


def _medication_reminder_row(user_id: int, due_at: datetime) -> reminder_models.Reminder:
    return reminder_models.Reminder(
        user_id=user_id,
        episode_id=None,
        kind=reminder_models.KIND_MEDICATION,
        status=reminder_models.STATUS_PENDING,
        due_at=due_at,
        title="氨氯地平 1 片",
        body="你录入的用法，请按医嘱或说明书使用。",
        snooze_count=0,
    )


def _insert(run_db: RunDb, row: reminder_models.Reminder) -> int:
    async def operation(session: AsyncSession) -> int:
        session.add(row)
        await session.commit()
        return int(row.id)

    result = run_db(operation)
    return result if isinstance(result, int) else 0


# ---- 按日列表 ----


def test_list_groups_by_day_and_kind(
    db_client: TestClient,
    user: dict[str, Any],
    run_db: RunDb,
) -> None:
    today = date.today()
    due = datetime.combine(today, datetime.min.time()) + timedelta(hours=8)
    row = _medication_reminder_row(1, due)
    reminder_id = _insert(run_db, row)

    response = db_client.get(f"/api/reminders?date={today.isoformat()}", headers=_auth(user))
    data = _body(response)["data"]

    assert data["pending_count"] == 1
    assert data["groups"]["medication"][0]["id"] == reminder_id
    assert data["groups"]["medication"][0]["title"] == "氨氯地平 1 片"

    other_day = db_client.get(
        f"/api/reminders?date={(today + timedelta(days=1)).isoformat()}",
        headers=_auth(user),
    )
    assert _body(other_day)["data"]["pending_count"] == 0

    bad_date = db_client.get("/api/reminders?date=not-a-date", headers=_auth(user))
    assert bad_date.status_code == 400


# ---- 用药与复查响应 ----


def test_medication_taken_and_snooze_limit(
    db_client: TestClient, user: dict[str, Any], run_db: RunDb
) -> None:
    row = _medication_reminder_row(1, datetime.now() + timedelta(hours=1))
    reminder_id = _insert(run_db, row)

    taken = db_client.post(
        f"/api/reminders/{reminder_id}/respond", json={"action": "taken"}, headers=_auth(user)
    )
    assert _body(taken)["data"]["status"] == "done"

    # 已处理再响应 → 409 + 3004
    again = db_client.post(
        f"/api/reminders/{reminder_id}/respond", json={"action": "taken"}, headers=_auth(user)
    )
    assert again.status_code == 409
    assert _body(again)["code"] == 3004


def test_snooze_twice_then_rejected(
    db_client: TestClient, user: dict[str, Any], run_db: RunDb
) -> None:
    row = _medication_reminder_row(1, datetime.now() + timedelta(hours=1))
    reminder_id = _insert(run_db, row)

    first = db_client.post(
        f"/api/reminders/{reminder_id}/respond", json={"action": "snooze"}, headers=_auth(user)
    )
    assert _body(first)["data"]["status"] == "pending"
    assert _body(first)["data"]["due_at"]

    second = db_client.post(
        f"/api/reminders/{reminder_id}/respond", json={"action": "snooze"}, headers=_auth(user)
    )
    assert _body(second)["data"]["status"] == "pending"

    third = db_client.post(
        f"/api/reminders/{reminder_id}/respond", json={"action": "snooze"}, headers=_auth(user)
    )
    assert third.status_code == 409
    assert _body(third)["code"] == 3004


def test_recheck_actions(
    db_client: TestClient,
    user: dict[str, Any],
    run_db: RunDb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_episode(db_client, user, monkeypatch, "clinic")
    saved = _save_episode(db_client, user, True)
    reminder_id = saved["reminder"]["id"]

    planned = db_client.post(
        f"/api/reminders/{reminder_id}/respond", json={"action": "planned"}, headers=_auth(user)
    )
    assert _body(planned)["data"]["status"] == "pending"

    invalid = db_client.post(
        f"/api/reminders/{reminder_id}/respond", json={"action": "flying"}, headers=_auth(user)
    )
    assert invalid.status_code == 400

    visited = db_client.post(
        f"/api/reminders/{reminder_id}/respond", json={"action": "visited"}, headers=_auth(user)
    )
    assert _body(visited)["data"]["status"] == "done"


def test_reminder_ownership(db_client: TestClient, user: dict[str, Any], run_db: RunDb) -> None:
    other = _register(db_client, "13800000002")
    row = _medication_reminder_row(1, datetime.now() + timedelta(hours=1))
    reminder_id = _insert(run_db, row)

    response = db_client.post(
        f"/api/reminders/{reminder_id}/respond",
        json={"action": "taken"},
        headers=_auth(other),
    )

    assert response.status_code == 404
    assert _body(response)["code"] == 3004


# ---- 随访第一层：八条规则 ----


def _followup_reminder(user_id: int, episode_id: int) -> reminder_models.Reminder:
    return reminder_models.Reminder(
        user_id=user_id,
        episode_id=episode_id,
        kind=reminder_models.KIND_FOLLOWUP,
        status=reminder_models.STATUS_PENDING,
        due_at=datetime.now() + timedelta(hours=48),
        title="上次不适的复评提醒",
        body=None,
        snooze_count=0,
    )


@pytest.mark.parametrize(
    ("answers", "note", "level"),
    [
        ({"relieved": "no", "visited": "no", "new_symptom": "no"}, "", "clinic"),
        ({"relieved": "worse", "visited": "no", "new_symptom": "no"}, "", "clinic"),
        ({"relieved": "no", "visited": "no", "new_symptom": "yes"}, "", "clinic"),
        ({"relieved": "no", "visited": "yes", "new_symptom": "no"}, "", "clinic"),
        ({"relieved": "yes", "visited": "no", "new_symptom": "no"}, "", "closed"),
        (
            {"relieved": "no", "visited": "yes", "new_symptom": "no"},
            "胸口疼，没有缓解，出汗",
            "emergency",
        ),
    ],
)
def test_followup_rules(
    db_client: TestClient,
    user: dict[str, Any],
    run_db: RunDb,
    monkeypatch: pytest.MonkeyPatch,
    answers: dict[str, str],
    note: str,
    level: str,
) -> None:
    _create_episode(db_client, user, monkeypatch, "self_observe")
    _save_episode(db_client, user, True)
    reminder_id = _insert(run_db, _followup_reminder(1, 1))

    async def no_supplement(request: dict[str, Any], session_id: str) -> dict[str, Any]:
        raise AssertionError("closed/emergency 档不应调第二层")

    monkeypatch.setattr(platform, "call_followup", no_supplement)

    response = db_client.post(
        f"/api/reminders/{reminder_id}/respond",
        json={"action": "answer", "answers": answers, "note": note},
        headers=_auth(user),
    )
    data = _body(response)["data"]

    assert data["advice"]["level"] == level
    assert data["supplement"] is None


def test_followup_clinic_with_valid_supplement(
    db_client: TestClient,
    user: dict[str, Any],
    run_db: RunDb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_episode(db_client, user, monkeypatch, "self_observe")
    _save_episode(db_client, user, True)
    reminder_id = _insert(run_db, _followup_reminder(1, 1))

    async def fake_call(request: dict[str, Any], session_id: str) -> dict[str, Any]:
        catalogs = request["catalogs"]
        assert isinstance(catalogs, dict)
        watch = catalogs["watch_for"]
        assert isinstance(watch, list) and watch
        return {
            "status": "supplement_ready",
            "supplement": {
                "watch_for": [watch[0]["text"]],
                "prepare_idx": [0],
                "next_question": "这两天夜里睡得怎么样？",
            },
        }

    monkeypatch.setattr(platform, "call_followup", fake_call)

    response = db_client.post(
        f"/api/reminders/{reminder_id}/respond",
        json={
            "action": "answer",
            "answers": {"relieved": "no", "visited": "no", "new_symptom": "no"},
        },
        headers=_auth(user),
    )
    data = _body(response)["data"]

    assert data["advice"]["level"] == "clinic"
    supplement = data["supplement"]
    assert supplement is not None
    assert supplement["watch_for"]
    assert supplement["prepare_idx"] == [0]


def test_followup_supplement_invalid_degrades(
    db_client: TestClient,
    user: dict[str, Any],
    run_db: RunDb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_episode(db_client, user, monkeypatch, "self_observe")
    _save_episode(db_client, user, True)
    reminder_id = _insert(run_db, _followup_reminder(1, 1))

    async def fake_call(request: dict[str, Any], session_id: str) -> dict[str, Any]:
        # watch_for 不在本轮目录里，prepare_idx 越界：整层应为 null
        return {
            "status": "supplement_ready",
            "supplement": {
                "watch_for": ["平台自编的观察项"],
                "prepare_idx": [99],
                "next_question": "",
            },
        }

    monkeypatch.setattr(platform, "call_followup", fake_call)

    response = db_client.post(
        f"/api/reminders/{reminder_id}/respond",
        json={
            "action": "answer",
            "answers": {"relieved": "no", "visited": "no", "new_symptom": "no"},
        },
        headers=_auth(user),
    )
    data = _body(response)["data"]

    assert data["advice"]["level"] == "clinic"
    assert data["supplement"] is None


def test_followup_rejects_bad_answers(
    db_client: TestClient,
    user: dict[str, Any],
    run_db: RunDb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_episode(db_client, user, monkeypatch, "self_observe")
    _save_episode(db_client, user, True)
    reminder_id = _insert(run_db, _followup_reminder(1, 1))

    response = db_client.post(
        f"/api/reminders/{reminder_id}/respond",
        json={
            "action": "answer",
            "answers": {"relieved": "maybe", "visited": "no", "new_symptom": "no"},
        },
        headers=_auth(user),
    )

    assert response.status_code == 400


# ---- 定时任务 ----


def test_scheduler_generates_idempotent_medication_reminders(
    db_client: TestClient, user: dict[str, Any], run_db: RunDb
) -> None:
    data = user
    med = db_client.post(
        "/api/medications",
        json={
            "name": "氨氯地平",
            "dosage_text": "1 片",
            "kind": "long_term",
            "started_on": "2026-01-01",
        },
        headers=_auth(data),
    )
    assert med.status_code == 200
    plan = db_client.post(
        "/api/medication-plans",
        json={"medication_id": 1, "times": ["08:00", "20:00"], "started_on": "2026-11-01"},
        headers=_auth(data),
    )
    assert plan.status_code == 200

    def generate() -> None:
        async def operation(session: AsyncSession) -> None:
            await generate_medication_reminders(session, date.today())

        run_db(operation)
        run_db(operation)  # 第二遍不翻倍

    generate()

    today = date.today().isoformat()
    listing = db_client.get(f"/api/reminders?date={today}", headers=_auth(data))
    records = _body(listing)["data"]["groups"]["medication"]

    assert len(records) == 2  # 重复执行不翻倍
    assert {record["title"] for record in records} == {"氨氯地平 1 片"}


def test_purge_deletes_expired_unsaved_episodes(
    db_client: TestClient,
    user: dict[str, Any],
    run_db: RunDb,
    db_execute: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_episode(db_client, user, monkeypatch, "self_observe")
    db_execute("UPDATE episode SET expires_at = now() - interval '1 day'")

    async def purge(session: AsyncSession) -> None:
        await purge_expired_episodes(session, datetime.now())

    run_db(purge)

    detail = db_client.get("/api/episodes/1", headers=_auth(user))
    assert detail.status_code == 404


def test_reminders_require_auth(db_client: TestClient) -> None:
    assert db_client.get("/api/reminders").status_code == 401
