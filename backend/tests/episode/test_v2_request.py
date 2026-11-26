"""triage request.v2 组装层：契约形状、边界校验与 #25 上下文。

全部合成数据。契约要点对齐 issue #23 的确认稿：answers 三动作、
understanding 不透明回传、history_context 与 Daily 16.8.4 同构。
"""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.clock import now_shanghai
from app.common.errors import BizException
from app.episode import models as episode_models
from app.episode import v2


def _raises_invalid(action: Any) -> None:
    with pytest.raises(BizException) as caught:
        action()
    assert caught.value.code is not None


def test_v2_request_shape_matches_contract() -> None:
    request = v2.build_v2_request(
        episode_id=12,
        request_id="ep12-4f8c9d22a1b7",
        complaint_text="我发烧了",
        answers=[
            {
                "answer_id": "a1",
                "question_id": "q1",
                "action": "answer",
                "text": "三天了，没吃过药",
            },
            {
                "answer_id": "a2",
                "question_id": None,
                "action": "answer",
                "text": "昨天量了大概38度",
            },
            {"answer_id": "a3", "question_id": "q2", "action": "skip", "text": ""},
        ],
        understanding=None,
        history_context={"consultations": [], "medications": []},
        profile_snapshot={"age": 68, "sex": "female"},
        red_flag_ids=[],
        asked_count=3,
        ask_limit=v2.ASK_LIMIT_INITIAL,
        skipped=False,
        base_revision=0,
    )

    assert request["schema_version"] == "clear-complaint.triage.request.v2"
    assert request["complaint_text"] == "我发烧了"
    assert request["answers"][1]["question_id"] is None
    assert request["understanding"] is None
    assert request["clarification"] == {"asked_count": 3, "limit": 10, "skipped": False}
    assert request["base_revision"] == 0
    # v1 的预提取字段全部不在请求里：理解归理解节点
    for removed in ("normalized", "self_attribution", "vitals_snapshot", "env"):
        assert removed not in request


def test_understanding_validation() -> None:
    assert v2.validate_understanding(None) is None
    assert v2.validate_understanding({"facts": {}}) == {"facts": {}}
    _raises_invalid(lambda: v2.validate_understanding(["not", "an", "object"]))
    oversized = {"blob": "x" * (v2.UNDERSTANDING_MAX_CHARS + 100)}
    _raises_invalid(lambda: v2.validate_understanding(oversized))


def test_answers_validation() -> None:
    base = {"question_id": "q1", "action": "answer", "text": "昨天开始"}
    assert v2.validate_answers([{"answer_id": "a1", **base}]) == [{"answer_id": "a1", **base}]
    # 主动补充、未知、跳过都合法；未知与跳过不转写成「没有」，原文是什么就传什么
    assert v2.validate_answers(
        [{"answer_id": "a1", "question_id": None, "action": "unknown", "text": ""}]
    )
    assert v2.validate_answers(
        [{"answer_id": "a1", "question_id": "q1", "action": "skip", "text": ""}]
    )
    _raises_invalid(lambda: v2.validate_answers([{"answer_id": "", **base}]))
    _raises_invalid(
        lambda: v2.validate_answers([{"answer_id": "a1", **base}, {"answer_id": "a1", **base}])
    )
    _raises_invalid(
        lambda: v2.validate_answers(
            [{"answer_id": "a1", "question_id": "q1", "action": "maybe", "text": "…"}]
        )
    )
    _raises_invalid(
        lambda: v2.validate_answers(
            [{"answer_id": "a1", "question_id": "q1", "action": "answer", "text": "x" * 501}]
        )
    )
    _raises_invalid(
        lambda: v2.validate_answers(
            [{"answer_id": "a1", "question_id": 7, "action": "answer", "text": "…"}]
        )
    )


def test_consultation_summary_truncates_and_composes() -> None:
    episode = episode_models.Episode(
        user_id=1,
        status="saved",
        complaint_text="发热",
        result={"triage": "clinic", "department_primary": "呼吸内科"},
    )
    summary = v2._consultation_summary(episode)
    assert "门诊" in summary and "呼吸内科" in summary
    long = episode_models.Episode(
        user_id=1,
        status="saved",
        complaint_text="长" * 2000,
        result={"triage": "clinic"},
    )
    assert len(v2._consultation_summary(long)) <= v2.SUMMARY_CHARS


def test_history_context_limits_and_exclusion(
    db_client: TestClient,
    run_db: Callable[[Callable[[AsyncSession], Awaitable[Any]]], Any],
) -> None:
    user = db_client.post(
        "/api/auth/register",
        json={
            "phone": "13800000123",
            "password": "passw0rd",
            "consent_version": "2026-11-01",
            "accept_privacy": True,
            "accept_sensitive": True,
        },
    )
    user_id = user.json()["data"]["user"]["id"]

    from app.common.clock import now_shanghai

    async def seed(session: AsyncSession) -> None:
        session.add_all(
            [
                episode_models.Episode(
                    user_id=user_id,
                    status="saved",
                    complaint_text=f"主诉{i}",
                    result={"triage": "clinic", "department_primary": "全科医学科"},
                    expires_at=now_shanghai() + timedelta(days=30),
                )
                for i in range(3)
            ]
        )
        await session.commit()

    run_db(seed)

    async def build(session: AsyncSession) -> dict[str, Any]:
        from app.common.clock import now_shanghai

        return await v2.build_history_context(session, user_id, now_shanghai())

    context = run_db(build)
    assert len(context["consultations"]) == 3
    assert context["medications"] == []
    top = context["consultations"][0]
    assert top["id"].startswith("ep")
    assert top["occurred_on"]
    assert "门诊" in top["summary"] and "全科医学科" in top["summary"]

    async def build_excluded(session: AsyncSession) -> dict[str, Any]:
        from sqlalchemy import select

        from app.common.clock import now_shanghai

        latest = (
            await session.execute(
                select(episode_models.Episode.id)
                .order_by(episode_models.Episode.id.desc())
                .limit(1)
            )
        ).scalar_one()
        return await v2.build_history_context(
            session, user_id, now_shanghai(), exclude_episode_id=latest
        )

    excluded = run_db(build_excluded)
    assert len(excluded["consultations"]) == 2

    async def aged_out(session: AsyncSession) -> None:
        from sqlalchemy import update

        from app.common.clock import now_shanghai

        await session.execute(
            update(episode_models.Episode).values(
                created_at=now_shanghai() - timedelta(days=v2.HISTORY_DAYS + 10)
            )
        )
        await session.commit()

    run_db(aged_out)
    empty = run_db(build)
    assert empty["consultations"] == []


def test_active_medications_brief_shape_and_limit(
    db_client: TestClient,
    run_db: Callable[[Callable[[AsyncSession], Awaitable[Any]]], Any],
) -> None:
    from datetime import date as date_type

    from app.archive import models as archive_models
    from app.archive import service as archive_service

    user = db_client.post(
        "/api/auth/register",
        json={
            "phone": "13800000124",
            "password": "passw0rd",
            "consent_version": "2026-11-01",
            "accept_privacy": True,
            "accept_sensitive": True,
        },
    )
    user_id = user.json()["data"]["user"]["id"]

    async def seed(session: AsyncSession) -> None:
        session.add_all(
            [
                archive_models.Medication(
                    user_id=user_id,
                    name=f"合成药{i}",
                    kind="long_term",
                    started_on=date_type(2026, 11, 1),
                    status="active" if i < v2.MEDICATION_LIMIT else "stopped",
                )
                for i in range(v2.MEDICATION_LIMIT + 3)
            ]
        )
        await session.commit()

    run_db(seed)

    async def brief(session: AsyncSession) -> list[Any]:
        return await archive_service.active_medications_brief(session, user_id, v2.MEDICATION_LIMIT)

    rows = run_db(brief)
    assert len(rows) == v2.MEDICATION_LIMIT
    # 只回 id/name/status 三项，且全部是 active
    assert set(rows[0]) == {"id", "name", "status"}
    assert all(row["status"] == "active" for row in rows)


def _blank_episode() -> episode_models.Episode:
    return episode_models.Episode(
        user_id=1, status="generating", complaint_text="我发烧了", expires_at=now_shanghai()
    )


def test_answer_ledger_ids_and_validation() -> None:
    episode = _blank_episode()
    first = v2.append_answer(episode, "q1", "answer", "昨天开始")
    second = v2.append_answer(episode, None, "answer", "补一句：大概38度")
    third = v2.append_answer(episode, "q2", "unknown", "")

    assert [first["answer_id"], second["answer_id"], third["answer_id"]] == ["a1", "a2", "a3"]
    assert second["question_id"] is None
    assert episode.raw_answers == [first, second, third]

    _raises_invalid(lambda: v2.append_answer(episode, "q1", "maybe", "…"))
    _raises_invalid(lambda: v2.append_answer(episode, "q1", "answer", "x" * 501))


def test_question_registry_counts_unique_only() -> None:
    episode = _blank_episode()
    assert v2.new_question_id(episode) == "q1"
    assert v2.register_question(episode, "q1", "onset", "什么时候开始的？", True)
    assert v2.asked_count(episode) == 1
    # 重复下发同一问题：不重复展示、不重复计数
    assert not v2.register_question(episode, "q1", "onset", "什么时候开始的？", True)
    assert v2.asked_count(episode) == 1

    assert v2.new_question_id(episode) == "q2"
    assert v2.register_question(episode, "q2", "other", "你说的A和B是同一个部位吗？", True)
    assert v2.asked_count(episode) == 2
    _raises_invalid(lambda: v2.register_question(episode, "q3", "vibes", "不合法的提问目的", True))


def test_ask_limit_switches_by_period() -> None:
    episode = _blank_episode()
    assert v2.ask_limit_for(episode) == v2.ASK_LIMIT_INITIAL
    v2.supersede_result(episode, {"triage": "clinic"}, {"degraded": False})
    assert v2.ask_limit_for(episode) == v2.ASK_LIMIT_REVISION


def test_result_supersede_history_cap_and_revisions() -> None:
    episode = _blank_episode()
    first = v2.supersede_result(episode, {"triage": "clinic", "mark": 0}, {"degraded": False})
    # 平台口径：首版结果即 revision=1；base_revision=0 表示尚无结果
    assert first == 1 and not episode.result_history

    second = v2.supersede_result(episode, {"triage": "clinic", "mark": 1}, {"degraded": False})
    assert second == 2
    assert episode.result_history == [
        {
            "revision": 1,
            "result": {"triage": "clinic", "mark": 0},
            "gate": {"degraded": False},
            "saved_at": None,
        }
    ]

    for mark in range(2, 7):
        v2.supersede_result(episode, {"triage": "clinic", "mark": mark}, {"degraded": False})
    # 只保留最近三版，最旧的被挤掉
    assert len(episode.result_history) == v2.RESULT_HISTORY_CAP
    assert [item["revision"] for item in episode.result_history] == [4, 5, 6]
    assert episode.revision == 7
    assert episode.result == {"triage": "clinic", "mark": 6}


def test_stale_revision_rejects_late_results() -> None:
    episode = _blank_episode()
    v2.supersede_result(episode, {"triage": "clinic"}, {})
    v2.supersede_result(episode, {"triage": "clinic"}, {})
    assert episode.revision == 2
    assert not v2.is_stale_revision(episode, 2)
    # 基于 1 版的迟到结果：当前已是 2 版，拒收
    assert v2.is_stale_revision(episode, 1)


def test_store_understanding_roundtrip_guard() -> None:
    episode = _blank_episode()
    v2.store_understanding(episode, {"facts": {"onset": "昨天"}})
    assert episode.understanding == {"facts": {"onset": "昨天"}}
    v2.store_understanding(episode, None)
    assert episode.understanding is None
    _raises_invalid(lambda: v2.store_understanding(episode, ["not-an-object"]))
