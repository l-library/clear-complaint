"""档案摘要组装（16.8.4）：薄档案不编造字段、问诊候选疾病不转确诊、快照稳定、条数上限。"""

from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.daily import archive as archive_module
from app.episode.models import Episode
from daily.support import RunDb, add_episode, add_profile

DAY = date(2026, 11, 23)


def _build(run_db: RunDb, user_id: int, report_date: date = DAY) -> dict[str, Any]:
    async def op(session: AsyncSession) -> dict[str, Any]:
        return await archive_module.build_health_archive(session, user_id, report_date)

    return dict(run_db(op))


def test_no_archive_yields_empty_fields_and_no_invented_guidance(
    run_db: RunDb, user_id: int
) -> None:
    archive = _build(run_db, user_id)

    assert archive["profile"] == {}
    assert archive["confirmed_conditions"] == []
    assert archive["consultations"] == []
    assert archive["medical_records"] == []
    # v1 没有「已确认照护安排」实体，恒为空；不能因为空就补一条默认建议
    assert archive["care_guidance"] == []
    assert len(archive["snapshot_id"]) == 64


def test_profile_and_saved_consultation_are_assembled(run_db: RunDb, user_id: int) -> None:
    add_profile(run_db, user_id, name="演示用户", birth_date=date(1958, 3, 4), sex="female")
    episode_id = add_episode(
        run_db,
        user_id,
        created_at=datetime.fromisoformat("2026-11-20T09:30:00+08:00"),
    )

    archive = _build(run_db, user_id)

    assert archive["profile"] == {"preferred_name": "演示用户", "age": 68, "sex": "female"}
    consultations = archive["consultations"]
    assert isinstance(consultations, list) and len(consultations) == 1
    entry = consultations[0]
    assert entry["id"] == f"ep{episode_id}"
    assert entry["occurred_on"] == "2026-11-20"
    # 只写主诉、档位、科室三项事实；候选疾病按 16.8.4 不得转成确诊
    assert "近三天咳嗽" in entry["summary"]
    assert "门诊" in entry["summary"] and "呼吸内科" in entry["summary"]
    assert "社区获得性肺炎" not in entry["summary"]


def test_partial_profile_only_submits_authorised_fields(run_db: RunDb, user_id: int) -> None:
    add_profile(run_db, user_id, name=None, birth_date=None, sex="undisclosed")

    archive = _build(run_db, user_id)

    assert archive["profile"] == {"sex": "undisclosed"}


def test_snapshot_id_is_stable_and_content_sensitive(run_db: RunDb, user_id: int) -> None:
    add_profile(run_db, user_id)
    first = _build(run_db, user_id)
    second = _build(run_db, user_id)
    assert first["snapshot_id"] == second["snapshot_id"]

    add_episode(run_db, user_id)
    third = _build(run_db, user_id)
    assert third["snapshot_id"] != first["snapshot_id"]


def test_unsaved_episodes_are_not_consultations(run_db: RunDb, user_id: int) -> None:
    add_episode(run_db, user_id, status="ready")
    add_episode(run_db, user_id, status="clarifying")

    archive = _build(run_db, user_id)

    assert archive["consultations"] == []


def test_consultation_cap_keeps_at_most_sixty(run_db: RunDb, user_id: int) -> None:
    for index in range(archive_module.CONSULTATION_LIMIT + 1):
        add_episode(run_db, user_id, complaint=f"主诉{index}")

    archive = _build(run_db, user_id)

    consultations = archive["consultations"]
    assert isinstance(consultations, list)
    assert len(consultations) == archive_module.CONSULTATION_LIMIT


def test_consultation_summary_is_capped(run_db: RunDb) -> None:
    # complaint_text 列只有 500 字，正常数据到不了 800；这道上限是给未来的
    # 病历摘要留的边界检查，用内存对象验证，不落库
    episode = Episode(user_id=1, status="saved", complaint_text="咳" * 2000)

    summary = archive_module._consultation_summary(episode)

    assert len(summary) == archive_module.SUMMARY_CHARS


def test_record_ids_cover_only_ids_present_in_the_archive(run_db: RunDb, user_id: int) -> None:
    episode_id = add_episode(run_db, user_id)
    archive = _build(run_db, user_id)

    ids = archive_module.record_ids(archive)

    assert ids == {f"ep{episode_id}"}
