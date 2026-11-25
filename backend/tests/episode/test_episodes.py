"""问诊主链路：创建、追问、生成、兜底、幂等、保存与删除。

平台调用全部打桩（app.episode.platform.call_triage），用例只验证后端行为：
红旗短路不碰平台、平台错误转兜底 done、引用逐字核验、幂等重放。
"""

import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.agent.client import invoke_workflow  # noqa: F401  确保客户端可导入
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.core.config import get_settings
from app.episode import platform

_POOL_CONTENT = "以鼻塞、流涕、喷嚏、咽痛为主要表现，全身症状较轻。"

_KEY = "0f14d0ab-9605-4a62-b89d-137cadb063aa"  # 固定的合法 UUID v4


def _body(response: Response) -> dict[str, Any]:
    payload: dict[str, Any] = response.json()
    return payload


def _draft_ready(
    triage: str = "clinic",
    department: str = "呼吸内科",
    conditions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if conditions is None:
        conditions = [_valid_condition()]
    return {
        "status": "draft_ready",
        "draft": {
            "triage": triage,
            "department_primary": department,
            "department_secondary": None,
            "conditions": conditions,
        },
        "output_list": [
            {
                "evidence_idx": 0,
                "document_name": "普通感冒规范诊治的专家共识",
                "subtitle": "临床表现",
                "content": _POOL_CONTENT,
            }
        ],
    }


def _valid_condition() -> dict[str, Any]:
    return {
        "name": "上呼吸道感染",
        "evidence": [
            {
                "evidence_idx": 0,
                "doc_title": "普通感冒规范诊治的专家共识",
                "section": "临床表现",
                "quote": "以鼻塞、流涕、喷嚏、咽痛为主要表现",
            }
        ],
    }


def _needs_clarification(fields: list[str]) -> dict[str, Any]:
    return {
        "status": "needs_clarification",
        "clarification_request": {
            "round": 1,
            "round_limit": 5,
            "question_fields": fields,
            "missing_fields": fields,
        },
    }


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


def _fill_profile(client: TestClient, data: dict[str, Any]) -> None:
    response = client.put(
        "/api/profile",
        json={"birth_date": "1990-06-12", "sex": "female"},
        headers=_auth(data),
    )
    assert response.status_code == 200, response.text


def _auth(data: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {data['tokens']['access_token']}"}


def _sse_headers(data: dict[str, Any], key: str = _KEY) -> dict[str, str]:
    return {**_auth(data), "Idempotency-Key": key}


def _parse_events(text: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        name = None
        raw = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                raw = line[len("data: ") :]
        if name is not None and raw is not None:
            payload: dict[str, Any] = json.loads(raw)
            events.append((name, payload))
    return events


def _names(events: list[tuple[str, dict[str, Any]]]) -> list[str]:
    return [name for name, _ in events]


def _post_episode(
    client: TestClient,
    data: dict[str, Any],
    complaint: str = "流鼻涕三天了，清水样，没有发热",
    key: str = _KEY,
) -> Response:
    with client.stream(
        "POST",
        "/api/episodes",
        json={"complaint": complaint},
        headers=_sse_headers(data, key),
    ) as response:
        response.read()
    result: Response = response
    return result


class Platform:
    """平台打桩：按调用顺序返回预设结果，并计数。"""

    def __init__(self, results: list[dict[str, Any] | Exception]) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, request: dict[str, Any], session_id: str) -> dict[str, Any]:
        self.calls.append(request)
        outcome = self.results.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def user(db_client: TestClient) -> dict[str, Any]:
    data = _register(db_client, "13800000001")
    _fill_profile(db_client, data)
    return data


# ---- 创建前置校验 ----


def test_create_requires_profile(db_client: TestClient, user: dict[str, Any]) -> None:
    data = _register(db_client, "13800000002")  # 未填档案

    response = _post_episode(db_client, data, key="11111111-2222-4333-8444-555555555555")

    assert response.status_code == 409
    assert _body(response)["code"] == 3001


def test_create_validates_complaint_and_key(db_client: TestClient, user: dict[str, Any]) -> None:
    empty = _post_episode(db_client, user, complaint="   ")
    assert empty.status_code == 400
    assert _body(empty)["code"] == 2001

    long = _post_episode(db_client, user, complaint="咳" * 501)
    assert long.status_code == 400
    assert _body(long)["code"] == 2002

    missing = db_client.post("/api/episodes", json={"complaint": "流鼻涕"}, headers=_auth(user))
    assert missing.status_code == 400

    bad = db_client.post(
        "/api/episodes", json={"complaint": "流鼻涕"}, headers=_sse_headers(user, key="not-a-uuid")
    )
    assert bad.status_code == 400


def test_create_requires_auth(db_client: TestClient) -> None:
    response = db_client.post("/api/episodes", json={"complaint": "流鼻涕"})
    assert response.status_code == 401


# ---- 红旗短路 ----


def test_red_flag_short_circuits_without_platform(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)

    response = _post_episode(db_client, user, complaint="胸口疼，没有缓解，出汗")
    text = response.read() if isinstance(response, str) else ""
    del text

    with db_client.stream(
        "POST",
        "/api/episodes",
        json={"complaint": "胸口疼，没有缓解，出汗"},
        headers=_sse_headers(user, "22222222-3333-4444-8555-666666666666"),
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)

    assert fake.calls == []  # 红旗不调模型
    names = _names(events)
    assert "question" not in names
    done = dict(events[-1][1])
    assert done["triage"] == "emergency"
    assert done["degraded"] is False
    assert done["gate"]["red_flags"]
    sections = {
        event[1]["section"]: event[1]["payload"] for event in events if event[0] == "result_section"
    }
    assert sections["department"]["department_primary"] == "急诊科"
    assert sections["disclaimer"]


# ---- 生成与兜底 ----


def test_draft_ready_streams_full_result(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流鼻涕三天了"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    names = _names(events)

    assert names[0] == "stage"
    assert "citation" in names
    assert names.count("result_section") == 5
    assert names[-1] == "done"
    done = dict(events[-1][1])
    assert done["triage"] == "clinic"
    assert done["conditions_count"] == 1
    assert done["degraded"] is False
    sections = {
        event[1]["section"]: event[1]["payload"] for event in events if event[0] == "result_section"
    }
    assert sections["triage"]["triage_label"] == "门诊"
    assert sections["conditions"][0]["name"] == "上呼吸道感染"
    assert sections["prep"]["bring"]

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "ready"
    assert detail["gate"]["citations_verified"] == 1
    assert detail["profile_snapshot"]["sex"] == "female"
    # normalize 的口语折算：流鼻涕 → 流涕（app/agent/normalize.py 的 COLLOQUIAL_MAP）
    assert detail["normalized"]["symptom"] == ["流涕三天了"]


def test_platform_unavailable_falls_back(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([BizException(ErrorCode.AGENTARTS_UNAVAILABLE)])
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流鼻涕三天了"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    done = dict(events[-1][1])

    assert events[-1][0] == "done"
    assert done["triage"] == "clinic"
    assert done["degraded"] is True
    sections = {
        event[1]["section"]: event[1]["payload"] for event in events if event[0] == "result_section"
    }
    assert sections["department"]["department_primary"] == "全科医学科"
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["gate"]["fallback"] is True


def test_invalid_draft_enum_falls_back(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready(triage="门诊")])
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流鼻涕三天了"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)

    assert dict(events[-1][1])["degraded"] is True


def test_unverified_citation_is_dropped(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    condition = {
        "name": "上呼吸道感染",
        "evidence": [
            {
                "evidence_idx": 0,
                "doc_title": "x",
                "section": "y",
                "quote": "这句在池子里完全找不到",
            }
        ],
    }
    fake = Platform([_draft_ready(conditions=[condition])])
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流鼻涕三天了"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    done = dict(events[-1][1])

    assert done["conditions_count"] == 0
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["result"]["conditions"] == []
    assert detail["gate"]["citations_dropped"] >= 1


def test_unknown_condition_name_is_dropped(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    condition = {
        "name": "神秘未知综合征X",
        "evidence": [
            {"evidence_idx": 0, "doc_title": "x", "section": "y", "quote": "以鼻塞、流涕为主要表现"}
        ],
    }
    fake = Platform([_draft_ready(conditions=[condition])])
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流鼻涕三天了"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    done = dict(_parse_events(body)[-1][1])

    assert done["conditions_count"] == 0


# ---- 追问 ----


def test_missing_medication_gets_a_second_round(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fields = ["onset", "duration", "location", "character", "associated_symptoms"]
    first = _needs_clarification(fields)
    first["clarification_request"]["missing_fields"] = fields + ["medication"]
    # io.5 契约：缺项补问走 needs_clarification；insufficient_evidence 恒为空检索
    second = _needs_clarification(["medication"])
    fake = Platform(
        [
            first,
            second,
            _draft_ready(),
        ]
    )
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="合成测试：鼻塞流涕", key=_KEY)
    answers = [
        {"field": "onset_at", "value": "两天前"},
        {"field": "duration_text", "value": "1–3 天"},
        {"field": "site", "value": "鼻部"},
        {"field": "nature", "value": "鼻塞"},
        {"field": "associated", "value": "流涕"},
    ]
    response = db_client.post(
        "/api/episodes/1/clarify",
        json={"answers": answers},
        headers=_sse_headers(user, "11111111-2222-4333-8444-555555555555"),
    )
    assert response.status_code == 200
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["clarify"]["round"] == 2
    assert [item["field"] for item in detail["clarify"]["questions"]] == ["medications_text"]
    assert fake.calls[1]["normalized"]["duration"] == "一至三天"
    assert detail["normalized"]["duration_text"] == "1–3 天"
    response = db_client.post(
        "/api/episodes/1/clarify",
        json={"answers": [{"field": "medications_text", "value": "不清楚"}]},
        headers=_sse_headers(user, "22222222-3333-4444-8555-666666666666"),
    )
    assert response.status_code == 200
    assert fake.calls[2]["normalized"]["medication"] == "unknown"
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "ready"


def test_empty_retrieval_insufficient_falls_back_without_asking(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """io.5：空检索重试一次后 insufficient_evidence，缺项未评估、不可补问。"""
    fake = Platform(
        [
            {
                "status": "insufficient_evidence",
                "error_code": "NO_RETRIEVAL_EVIDENCE",
                "missing_fields": [],
                "unknown_fields": [],
                "clarification_request": None,
                "draft": None,
                "needs_backend_fallback": True,
                "retrieval": {
                    "attempts": 2,
                    "retry_used": True,
                    "status": "empty",
                    "field_status_evaluated": False,
                },
            }
        ]
    )
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST",
        "/api/episodes",
        json={"complaint": "合成测试：鼻塞流涕"},
        headers=_sse_headers(user),
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    done = dict(events[-1][1])

    assert events[-1][0] == "done"
    assert done["degraded"] is True
    # 只调了一次平台：空检索不触发补问轮
    assert len(fake.calls) == 1
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "ready"
    assert detail["gate"]["retrieval"] == {
        "attempts": 2,
        "retry_used": True,
        "status": "empty",
        "field_status_evaluated": False,
    }


def test_needs_clarification_then_answer(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform(
        [
            # 平台字段名：character 对应公开的 nature
            _needs_clarification(["duration", "character"]),
            _draft_ready(triage="clinic", department="呼吸内科"),
        ]
    )
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "我流鼻涕"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    question = dict([event for event in events if event[0] == "question"][0][1])

    assert question["round"] == 1
    fields = [q["field"] for q in question["questions"]]
    assert fields == ["duration_text", "nature"]
    assert question["questions"][0]["options"]
    assert "done" not in _names(events)

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "clarifying"

    with db_client.stream(
        "POST",
        "/api/episodes/1/clarify",
        json={"answers": [{"field": "duration_text", "value": "三天"}]},
        headers=_sse_headers(user, "33333333-4444-4555-8666-777777777777"),
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)

    assert events[-1][0] == "done"
    second_request = fake.calls[1]
    assert second_request["normalized"]["duration"] == "三天"
    assert second_request["clarification"]["round"] == 1

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["normalized"]["duration_text"] == "三天"
    assert detail["gate"]["clarify_rounds"] == 1


def test_clarify_rejects_unknown_field(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_needs_clarification(["duration"])])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="我流鼻涕", key="44444444-5555-4666-8777-888888888888")

    response = db_client.post(
        "/api/episodes/1/clarify",
        json={"answers": [{"field": "nature", "value": "胀痛"}]},
        headers=_sse_headers(user, "55555555-6666-4777-8888-999999999999"),
    )

    assert response.status_code == 400
    assert _body(response)["code"] == 2007


def test_clarify_answer_can_raise_red_flag(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_needs_clarification(["associated_symptoms"])])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="我流鼻涕", key="66666666-7777-4888-8999-aaaaaaaaaaaa")

    with db_client.stream(
        "POST",
        "/api/episodes/1/clarify",
        json={"answers": [{"field": "associated", "value": "胸口疼得厉害，出冷汗"}]},
        headers=_sse_headers(user, "77777777-8888-4999-8aaa-bbbbbbbbbbbb"),
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    done = dict(events[-1][1])

    assert events[-1][0] == "done"
    assert done["triage"] == "emergency"
    assert done["gate"]["red_flags"]
    assert len(fake.calls) == 1  # 答案命中红旗后不再调平台


def test_skip_clarify_generates(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_needs_clarification(["duration"]), _draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="我流鼻涕", key="88888888-9999-4000-8bbb-cccccccccccc")

    with db_client.stream(
        "POST",
        "/api/episodes/1/skip-clarify",
        json=None,
        headers=_sse_headers(user, "99999999-aaaa-4111-8ccc-dddddddddddd"),
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)

    assert events[-1][0] == "done"
    assert fake.calls[1]["clarification"]["skipped"] is True


def test_clarify_requires_clarifying_state(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    response = db_client.post(
        "/api/episodes/1/clarify",
        json={"answers": [{"field": "duration_text", "value": "三天"}]},
        headers=_sse_headers(user, "aaaaaaa1-bbbb-4222-8ddd-eeeeeeeeeeee"),
    )

    assert response.status_code == 409
    assert _body(response)["code"] == 2005


# ---- 重试 ----


def test_retry_after_unexpected_failure(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([RuntimeError("平台侧炸了"), _draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流鼻涕三天了"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)

    assert events[-1][0] == "error"
    assert dict(events[-1][1])["retryable"] is True
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "failed"

    with db_client.stream(
        "POST",
        "/api/episodes/1/retry",
        json=None,
        headers=_sse_headers(user, "bbbbbbb1-cccc-4333-8eee-ffffffffffff"),
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)

    assert events[-1][0] == "done"
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "ready"


def test_retry_rejects_ready_episode(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    response = db_client.post(
        "/api/episodes/1/retry",
        json=None,
        headers=_sse_headers(user, "ccccccc1-dddd-4444-8fff-000000000000"),
    )

    assert response.status_code == 409
    assert _body(response)["code"] == 2005


# ---- 幂等 ----


def test_same_key_replays_without_second_call(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流鼻涕三天了"}, headers=_sse_headers(user)
    ) as stream:
        first = stream.read().decode()

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流鼻涕三天了"}, headers=_sse_headers(user)
    ) as stream:
        second = stream.read().decode()

    assert len(fake.calls) == 1
    assert _parse_events(second)[-1][0] == "done"
    assert _parse_events(first)[-1][0] == "done"


def test_same_key_different_body_conflicts(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    response = db_client.post(
        "/api/episodes",
        json={"complaint": "另一次完全不同的主诉"},
        headers=_sse_headers(user),
    )

    assert response.status_code == 409
    assert _body(response)["code"] == 2006


# ---- 读端点与删除 ----


def test_detail_hides_other_users_and_expired(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    other = _register(db_client, "13800000003")
    response = db_client.get("/api/episodes/1", headers=_auth(other))
    assert response.status_code == 404
    assert _body(response)["code"] == 2004

    db_client.app  # noqa: B018
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    expires = detail["episode"]["expires_at"]
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", expires)


def test_expired_episode_is_404(
    db_client: TestClient,
    user: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    db_execute: Any,
) -> None:
    fake = Platform([_draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)
    db_execute("UPDATE episode SET expires_at = now() - interval '1 day'")

    response = db_client.get("/api/episodes/1", headers=_auth(user))

    assert response.status_code == 404
    assert _body(response)["code"] == 2004


def test_list_filters_and_pages(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready(triage="self_observe", department="全科医学科"), _draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="第一次", key="ddddddd1-eeee-4555-8000-111111111111")
    _post_episode(db_client, user, complaint="第二次", key="eeeeeee1-ffff-4666-8111-222222222222")

    response = db_client.get("/api/episodes", headers=_auth(user))
    data = _body(response)["data"]
    assert data["total"] == 2
    assert data["records"][0]["complaint_excerpt"] == "第二次"

    filtered = db_client.get("/api/episodes?triage=self_observe", headers=_auth(user))
    assert _body(filtered)["data"]["total"] == 1

    paginated = db_client.get("/api/episodes?page=2&size=1", headers=_auth(user))
    assert _body(paginated)["data"]["total"] == 2
    assert len(_body(paginated)["data"]["records"]) == 1


# ---- 保存与提醒 ----


def test_save_clinic_creates_recheck(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready(triage="clinic", department="呼吸内科")])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    response = db_client.post(
        "/api/episodes/1/save", json={"save": True, "reminder": True}, headers=_auth(user)
    )
    data = _body(response)["data"]

    assert data["saved_at"]
    assert data["reminder"]["kind"] == "recheck"
    assert data["reminder"]["due_at"].endswith("09:00:00")

    again = db_client.post(
        "/api/episodes/1/save", json={"save": True, "reminder": True}, headers=_auth(user)
    )
    assert _body(again)["data"]["saved_at"] == data["saved_at"]


def test_save_self_observe_creates_followup(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready(triage="self_observe", department="全科医学科")])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    response = db_client.post(
        "/api/episodes/1/save", json={"save": True, "reminder": True}, headers=_auth(user)
    )
    data = _body(response)["data"]

    assert data["reminder"]["kind"] == "followup"


def test_save_emergency_has_no_reminder(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready(triage="emergency", department="急诊科")])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    response = db_client.post(
        "/api/episodes/1/save", json={"save": True, "reminder": True}, headers=_auth(user)
    )

    assert _body(response)["data"]["reminder"] is None


def test_save_rejects_out_of_range_recheck_date(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready(triage="clinic", department="呼吸内科")])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    response = db_client.post(
        "/api/episodes/1/save",
        json={"save": True, "reminder": True, "recheck_date": "2030-01-01"},
        headers=_auth(user),
    )

    assert response.status_code == 400
    assert "recheck_date" in _body(response)["message"]


def test_delete_removes_episode(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    response = db_client.delete("/api/episodes/1", headers=_auth(user))
    assert response.status_code == 200

    detail = db_client.get("/api/episodes/1", headers=_auth(user))
    assert detail.status_code == 404
