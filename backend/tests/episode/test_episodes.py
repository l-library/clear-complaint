"""问诊主链路：创建、追问、生成、兜底、幂等、保存与删除。

平台调用全部打桩（app.episode.platform.call_triage），用例只验证后端行为：
红旗短路不碰平台、平台错误转兜底 done、引用逐字核验、幂等重放。
"""

import json
import re
from collections.abc import Awaitable, Callable
from datetime import timedelta
from functools import partial
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import crisis
from app.agent.client import invoke_workflow  # noqa: F401  确保客户端可导入
from app.agent.normalize import normalize
from app.common.clock import now_shanghai
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.core.config import get_settings
from app.episode import compose, platform, v2
from app.episode import models as episode_models
from app.reminder import models as reminder_models

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
        "understanding": {},
        "normalized": {"symptom": "发热", "onset": None, "duration": None},
        "self_attribution": [],
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


def _question_response(
    purpose: str = "duration",
    text: str = "这次不舒服持续多久了？",
    status: str = "needs_clarification",
) -> dict[str, Any]:
    """单问响应：question_id 为空由后端赋号（契约第 3 节）。"""
    return {
        "status": status,
        "understanding": {},
        "normalized": {"symptom": "发热"},
        "self_attribution": [],
        "question": {"question_id": None, "purpose": purpose, "text": text, "can_skip": True},
        "draft": None,
    }


def _understood(base: dict[str, Any], **facts: str) -> dict[str, Any]:
    """预置 understanding：把测试放到指定问答阶段，事实来源都是合成原文。"""
    payload = dict(base)
    payload["understanding"] = {
        "schema_version": "clear-complaint.triage.understanding.v1",
        "facts": {key: {"status": "known", "value": value} for key, value in facts.items()},
    }
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
        # v2 回显：真实平台会带这三个关联字段，打桩缺省时自动补齐
        outcome.setdefault("schema_version", "clear-complaint.triage.workflow.v2")
        outcome.setdefault("workflow_version", "2026-11-26.mainflow-io.6")
        outcome.setdefault("request_id", request["request_id"])
        outcome.setdefault("episode_id", request["episode_id"])
        outcome.setdefault("base_revision", request["base_revision"])
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
    assert detail["episode"]["status"] == "saved"
    assert detail["gate"]["citations_verified"] == 1
    assert detail["profile_snapshot"]["sex"] == "female"
    # v2：normalized 是理解输出的回填；首版结果即 revision=1（平台口径）
    assert detail["normalized"]["symptom"] == ["发热"]
    assert detail["episode"]["revision"] == 1


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


def test_unverified_citation_deletes_conclusion(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """约束四：核不上的条目删除；仅剩的候选也被删光时不输出档位与科室。"""
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
    names = _names(events)
    done = dict(events[-1][1])

    # 删空不出档：done 不带档位，流里没有任何分诊段落
    assert events[-1][0] == "done"
    assert done["triage"] is None
    assert done["conditions_count"] == 0
    assert done["degraded"] is False
    assert done["gate"]["no_conclusion"] is True
    assert "result_section" not in names
    notices = [dict(event[1]) for event in events if event[0] == "notice"]
    assert notices[-1]["kind"] == "no_conclusion"
    assert notices[-1]["text"] == compose.NO_CONCLUSION_NOTICE

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["result"] is None
    assert detail["episode"]["status"] == "saved"
    # 坏证据一条 + 删空的条件本身又记一次：单条件删空共记 2 次
    assert detail["gate"]["citations_dropped"] == 2
    assert detail["gate"]["citations_verified"] == 0
    assert detail["gate"]["no_conclusion"] is True


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
    events = _parse_events(body)
    done = dict(events[-1][1])

    # 词表外的病名删除；删空同样不出档
    assert done["conditions_count"] == 0
    assert done["triage"] is None
    assert "result_section" not in _names(events)


def test_all_conditions_deleted_publishes_no_conclusion(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """B02-stop 复现：平台删光候选后仍回 draft_ready，后端不得出档。"""
    bad_quote = {"evidence_idx": 0, "doc_title": "x", "section": "y", "quote": "编造的引文"}
    conditions = [
        {"name": "上呼吸道感染", "evidence": [dict(bad_quote)]},
        {"name": "急性鼻窦炎", "evidence": [dict(bad_quote)]},
    ]
    fake = Platform([_draft_ready(conditions=conditions)])
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流鼻涕三天了"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    done = dict(events[-1][1])

    assert done["triage"] is None
    assert done["conditions_count"] == 0
    assert done["gate"]["citations_dropped"] == 4
    assert done["gate"]["no_conclusion"] is True


def test_zero_candidate_draft_still_publishes_result(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """删空不出档只看删除致空：平台没给候选（conditions 从头为空）维持出档。"""
    fake = Platform([_draft_ready(conditions=[])])
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "流鼻涕三天了"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    done = dict(events[-1][1])

    assert done["triage"] == "clinic"
    assert done["conditions_count"] == 0
    assert done["degraded"] is False
    assert done["gate"]["no_conclusion"] is False
    assert done["gate"]["citations_dropped"] == 0
    sections = {
        event[1]["section"]: event[1]["payload"] for event in events if event[0] == "result_section"
    }
    assert sections["triage"]["triage_label"] == "门诊"
    assert sections["department"]["department_primary"] == "呼吸内科"
    assert sections["conditions"] == []

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["result"]["triage"] == "clinic"
    assert detail["result"]["conditions"] == []
    assert detail["gate"]["no_conclusion"] is False


# ---- 追问 ----


def test_medication_question_single_round_flow(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """v2 单问流程：一次一问、答案原文进台账、平台收到累计回答。"""
    fake = Platform(
        [
            _question_response("medication", "这次生病后用过什么药吗？"),
            _draft_ready(),
        ]
    )
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="合成测试：鼻塞流涕", key=_KEY)

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "clarifying"
    assert detail["clarify"]["pending"]["purpose"] == "medication"
    assert detail["clarify"]["asked_count"] == 1

    response = db_client.post(
        "/api/episodes/1/clarify",
        json={"question_id": "q1", "action": "unknown", "text": ""},
        headers=_sse_headers(user, "11111111-2222-4333-8444-555555555555"),
    )
    assert response.status_code == 200
    # 第二次调用带累计台账：unknown 动作原样传递，不转成「没有」
    assert fake.calls[1]["answers"] == [
        {"answer_id": "a1", "question_id": "q1", "action": "unknown", "text": ""}
    ]
    assert fake.calls[1]["base_revision"] == 0
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "saved"


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
    assert detail["episode"]["status"] == "saved"
    assert detail["gate"]["retrieval"] == {
        "attempts": 2,
        "retry_used": True,
        "status": "empty",
        "field_status_evaluated": False,
    }


def test_single_question_then_answer(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform(
        [
            _question_response("duration", "这次不舒服持续多久了？"),
            _draft_ready(triage="clinic", department="呼吸内科"),
        ]
    )
    monkeypatch.setattr(platform, "call_triage", fake)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "我流鼻涕"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    questions = [event for event in events if event[0] == "question"]
    assert len(questions) == 1, "单问协议：一次调用只下发一个问题"
    question = dict(questions[0][1])

    # 后端赋号：question_id 稳定，答案凭它关联
    assert question["question_id"] == "q1"
    assert question["purpose"] == "duration"
    assert question["text"] == "这次不舒服持续多久了？"
    assert question["can_skip"] is True
    assert "done" not in _names(events)

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "clarifying"

    with db_client.stream(
        "POST",
        "/api/episodes/1/clarify",
        json={"question_id": "q1", "action": "answer", "text": "三天了"},
        headers=_sse_headers(user, "33333333-4444-4555-8666-777777777777"),
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)

    assert events[-1][0] == "done"
    second_request = fake.calls[1]
    # 原文进：答案逐字进台账，后端不做字段折算
    assert second_request["answers"] == [
        {"answer_id": "a1", "question_id": "q1", "action": "answer", "text": "三天了"}
    ]
    assert second_request["clarification"]["asked_count"] == 1

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "saved"
    # understanding 回传验证由真实联调覆盖；这里验证回填展示来自理解输出
    assert detail["normalized"]["symptom"] == ["发热"]


def test_answer_rejects_wrong_question_id(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_question_response("duration")])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="我流鼻涕", key="44444444-5555-4666-8777-888888888888")

    response = db_client.post(
        "/api/episodes/1/clarify",
        json={"question_id": "q9", "action": "answer", "text": "三天"},
        headers=_sse_headers(user, "55555555-6666-4777-8888-999999999999"),
    )

    assert response.status_code == 400
    assert _body(response)["code"] == 2007


def test_answer_can_raise_red_flag(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_question_response("associated_symptoms", "还有别的不舒服吗？")])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="我流鼻涕", key="66666666-7777-4888-8999-aaaaaaaaaaaa")

    with db_client.stream(
        "POST",
        "/api/episodes/1/clarify",
        json={"question_id": "q1", "action": "answer", "text": "胸口疼得厉害，出冷汗"},
        headers=_sse_headers(user, "77777777-8888-4999-8aaa-bbbbbbbbbbbb"),
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    done = dict(events[-1][1])

    assert events[-1][0] == "done"
    assert done["triage"] == "emergency"
    assert done["gate"]["red_flags"]
    assert len(fake.calls) == 1  # 答案命中红旗后不再调平台

    # 台账保留原文：红旗短路不清回答记录
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "saved"


def test_skip_clarify_generates(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_question_response("duration"), _draft_ready()])
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
    assert fake.calls[1]["answers"] == []


def test_answer_requires_valid_state(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    # 已完成（saved）的问诊：带问题号的回答被拒，主动补充必须 question_id=null
    response = db_client.post(
        "/api/episodes/1/clarify",
        json={"question_id": "q1", "action": "answer", "text": "三天"},
        headers=_sse_headers(user, "aaaaaaa1-bbbb-4222-8ddd-eeeeeeeeeeee"),
    )
    assert response.status_code == 409
    assert _body(response)["code"] == 2005

    # 合法的主动补充：走同一端点，question_id 为 null
    with db_client.stream(
        "POST",
        "/api/episodes/1/clarify",
        json={"question_id": None, "action": "answer", "text": "补充：还有点咳嗽"},
        headers=_sse_headers(user, "aaaaaaa2-bbbb-4222-8ddd-eeeeeeeeeeee"),
    ) as stream:
        stream.read()
    assert fake.calls[1]["answers"][-1]["question_id"] is None
    assert fake.calls[1]["base_revision"] == 1


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
    assert detail["episode"]["status"] == "saved"


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


async def _episode_reminders(
    session: AsyncSession, episode_id: int
) -> list[reminder_models.Reminder]:
    rows = await session.execute(
        select(reminder_models.Reminder).where(reminder_models.Reminder.episode_id == episode_id)
    )
    return list(rows.scalars())


def test_clinic_generation_auto_archives_and_creates_recheck(
    db_client: TestClient,
    user: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    run_db: Callable[[Callable[[AsyncSession], Awaitable[Any]]], Any],
) -> None:
    fake = Platform([_draft_ready(triage="clinic", department="呼吸内科")])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]

    # 生成完成即归档，不依赖任何手动确认（issue #24）
    assert detail["episode"]["status"] == "saved"
    assert detail["episode"]["saved_at"]

    reminders = run_db(partial(_episode_reminders, episode_id=1))
    assert len(reminders) == 1
    assert reminders[0].kind == "recheck"
    assert reminders[0].status == "pending"
    # 默认复查提醒：episode.created_at + 3 天的 09:00 上海时间（策略在后端，前端不再挑日期）
    assert reminders[0].due_at.astimezone(ZoneInfo("Asia/Shanghai")).hour == 9

    # 同一幂等键重放不重复归档、不翻倍提醒
    _post_episode(db_client, user)
    reminders_again = run_db(partial(_episode_reminders, episode_id=1))
    assert len(reminders_again) == 1


def test_self_observe_generation_creates_followup(
    db_client: TestClient,
    user: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    run_db: Callable[[Callable[[AsyncSession], Awaitable[Any]]], Any],
) -> None:
    fake = Platform([_draft_ready(triage="self_observe", department="全科医学科")])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "saved"

    reminders = run_db(partial(_episode_reminders, episode_id=1))
    assert len(reminders) == 1
    assert reminders[0].kind == "followup"


def test_emergency_generation_archives_without_reminder(
    db_client: TestClient,
    user: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    run_db: Callable[[Callable[[AsyncSession], Awaitable[Any]]], Any],
) -> None:
    fake = Platform([_draft_ready(triage="emergency", department="急诊科")])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user)

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]

    # 急诊档照常归档，但不建提醒：去急诊不需要应用提醒
    assert detail["episode"]["status"] == "saved"
    assert run_db(partial(_episode_reminders, episode_id=1)) == []


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


# ---- v2 状态机：三出口与修订（issue #23） ----


def _coverage_response(triage: str, department: str = "皮肤科") -> dict[str, Any]:
    return {
        "status": "out_of_coverage",
        "understanding": {},
        "normalized": {"symptom": "皮疹"},
        "self_attribution": [],
        "question": None,
        "draft": {
            "triage": triage,
            "department_primary": department,
            "department_secondary": None,
            "conditions": [],
        },
        "output_list": [],
    }


def test_out_of_coverage_valve_lifts_self_observe(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_coverage_response("self_observe")])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="合成测试：皮肤起了红点", key=_KEY)

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    # 单向阀：无引用的 self_observe 抬到 clinic，conditions 整节空
    assert detail["result"]["triage"] == "clinic"
    assert detail["result"]["out_of_coverage"] is True
    assert detail["result"]["conditions"] == []
    assert detail["gate"]["out_of_coverage"] is True
    assert detail["episode"]["status"] == "saved"


def test_out_of_coverage_keeps_emergency(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([_coverage_response("emergency", "急诊科")])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="合成测试：剧烈头痛", key=_KEY)

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["result"]["triage"] == "emergency"


def test_not_understood_with_question_forwards_single_question(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform(
        [
            _question_response("other", "想说说哪里不舒服吗？", status="not_understood"),
        ]
    )
    monkeypatch.setattr(platform, "call_triage", fake)
    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "我今天吃了火锅"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    questions = [event for event in events if event[0] == "question"]

    # 没听懂版：对话式追问，不吐分诊模板
    assert len(questions) == 1
    assert questions[0][1]["not_understood"] is True
    assert "done" not in _names(events)
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["result"] is None


def test_not_understood_without_question_ends_gently(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform([{"status": "not_understood", "question": None, "understanding": {}}])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="asdfgh", key=_KEY)

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["result"] is None
    assert detail["gate"]["not_understood"] is True


def test_supplement_after_result_creates_revision(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Platform(
        [
            _draft_ready(triage="clinic", department="呼吸内科"),
            _draft_ready(triage="clinic", department="呼吸内科"),
        ]
    )
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="合成测试：发热", key=_KEY)
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["revision"] == 1

    # 结果后主动补充：question_id=null，基于当前修订（base_revision=1）
    with db_client.stream(
        "POST",
        "/api/episodes/1/clarify",
        json={"question_id": None, "action": "answer", "text": "补充：今天开始咳嗽了"},
        headers=_sse_headers(user, "bbbbbbb1-cccc-4ddd-8eee-ffffffffffff"),
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    assert events[-1][0] == "done"

    assert fake.calls[1]["base_revision"] == 1
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    # 旧版本保留为可回看历史，saved_at 不随修订重置
    assert detail["episode"]["revision"] == 2
    assert detail["result_history"][0]["revision"] == 1
    assert detail["result_history"][0]["result"]["triage"] == "clinic"


def test_stale_revision_result_is_discarded(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    late = _draft_ready(triage="self_observe", department="全科医学科")
    late["base_revision"] = 0  # 基于旧基线（尚无结果）的迟到结果
    fake = Platform([_draft_ready(triage="clinic", department="呼吸内科"), late])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="合成测试：发热", key=_KEY)

    with db_client.stream(
        "POST",
        "/api/episodes/1/clarify",
        json={"question_id": None, "action": "answer", "text": "补充：咳嗽加重"},
        headers=_sse_headers(user, "ccccccc1-dddd-4eee-8fff-aaaaaaaaaaaa"),
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)

    # 迟到结果被丢弃：播当前已落库的结论，revision 不推进
    done = dict(events[-1][1])
    assert done["triage"] == "clinic"
    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["episode"]["revision"] == 1
    assert detail["result"]["triage"] == "clinic"


def test_ask_limit_forces_stop_before_platform_call(
    db_client: TestClient,
    user: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    run_db: Callable[[Callable[[AsyncSession], Awaitable[Any]]], Any],
) -> None:
    """B02：到达周期上限后整体停止补问，工作流按现有信息收尾，不硬停。"""
    user_id = user["user"]["id"] if isinstance(user, dict) and "user" in user else 1
    episode = episode_models.Episode(
        user_id=user_id,
        status="clarifying",
        complaint_text="合成测试：发热",
        raw_answers=[
            {"answer_id": f"a{i + 1}", "question_id": f"q{i + 1}", "action": "answer", "text": "答"}
            for i in range(v2.ASK_LIMIT_INITIAL)
        ],
        clarify_state={
            "asked_count": v2.ASK_LIMIT_INITIAL,
            "skipped": False,
            "questions": {f"q{i + 1}": {"purpose": "other"} for i in range(v2.ASK_LIMIT_INITIAL)},
            "pending_question_id": f"q{v2.ASK_LIMIT_INITIAL}",
            "pending": {
                "question_id": f"q{v2.ASK_LIMIT_INITIAL}",
                "purpose": "other",
                "text": "还想补充什么吗？",
                "can_skip": True,
            },
        },
        expires_at=now_shanghai() + timedelta(days=30),
    )

    async def seed(session: AsyncSession) -> int:
        session.add(episode)
        await session.commit()
        return episode.id

    episode_id = run_db(seed)
    fake = Platform([_draft_ready(triage="clinic", department="呼吸内科")])
    monkeypatch.setattr(platform, "call_triage", fake)

    # 上限已到：回答触发的下一轮调用必须带 skipped=true
    with db_client.stream(
        "POST",
        f"/api/episodes/{episode_id}/clarify",
        json={"question_id": f"q{v2.ASK_LIMIT_INITIAL}", "action": "answer", "text": "没了"},
        headers=_sse_headers(user),
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)

    assert events[-1][0] == "done"
    assert fake.calls[0]["clarification"]["skipped"] is True
    assert fake.calls[0]["clarification"]["asked_count"] == v2.ASK_LIMIT_INITIAL
    detail = _body(db_client.get(f"/api/episodes/{episode_id}", headers=_auth(user)))["data"]
    assert detail["episode"]["status"] == "saved"


def test_crisis_short_circuits_at_intake(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """危机命中：不调工作流、固定应对走 safety 事件、不进分诊（issue #23 第 6 节）。"""
    synthetic = (
        crisis.CrisisHit(rule_id="CR01", name="自伤意图", triggers=(normalize("不想活"),)),
    )
    monkeypatch.setattr(crisis, "rules", lambda: synthetic)

    no_platform = Platform([])
    monkeypatch.setattr(platform, "call_triage", no_platform)

    with db_client.stream(
        "POST", "/api/episodes", json={"complaint": "我最近不想活了"}, headers=_sse_headers(user)
    ) as stream:
        body = stream.read().decode()
    events = _parse_events(body)
    names = _names(events)

    assert no_platform.calls == [], "危机短路不得调用平台"
    assert "safety" in names
    safety = dict([event for event in events if event[0] == "safety"][0][1])
    assert safety["kind"] == "crisis"
    assert any("12356" in line for line in safety["copy"])
    # 不是分诊结论：没有 result_section
    assert "result_section" not in names

    detail = _body(db_client.get("/api/episodes/1", headers=_auth(user)))["data"]
    assert detail["result"] is None
    assert detail["gate"]["crisis"]["kind"] == "crisis"
    assert detail["episode"]["status"] == "saved"


def test_answer_idempotent_replay_calls_platform_once(
    db_client: TestClient, user: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """同键同文（含原话）幂等重放：平台只被调用一次。"""
    fake = Platform([_question_response("duration"), _draft_ready()])
    monkeypatch.setattr(platform, "call_triage", fake)
    _post_episode(db_client, user, complaint="我流鼻涕", key=_KEY)

    for _ in range(2):
        db_client.post(
            "/api/episodes/1/clarify",
            json={"question_id": "q1", "action": "answer", "text": "三天了"},
            headers=_sse_headers(user, "ddddddd1-eeee-4fff-8aaa-bbbbbbbccccc"),
        )
    assert len(fake.calls) == 2  # 首问 + 一次回答；重放未再调用
