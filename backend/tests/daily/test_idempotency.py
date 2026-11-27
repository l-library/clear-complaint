"""幂等与快照：同版本更新覆盖、升版另存、迟到结果不覆盖新报告、快照哈希随输入变化。"""

from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.daily import service
from daily.support import (
    DAY,
    WORKFLOW_VERSION,
    RunDb,
    add_episode,
    generate,
    platform_result,
    snapshot,
    stored,
    stub_platform,
)


def _summary(text: str) -> dict[str, Any]:
    return {"title": "今天的健康小结", "closing": text}


def test_same_version_updates_in_place(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    texts = iter(["第一版", "第二版"])
    stub_platform(
        monkeypatch,
        lambda request: platform_result(request, summary=_summary(next(texts))),
    )

    first = generate(run_db, user_id)
    second = generate(run_db, user_id)

    rows = stored(run_db, user_id)
    assert len(rows) == 1
    assert rows[0]["id"] == first["id"] == second["id"]
    assert rows[0]["summary"] == _summary("第二版")
    # 输入完全一致（合成数据按用户＋日期确定），快照哈希不变
    assert rows[0]["input_snapshot_hash"] == first["input_snapshot_hash"]


def test_new_workflow_version_keeps_one_row_per_version(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    versions = iter([WORKFLOW_VERSION, "2026-12-01.daily-companion.3"])
    stub_platform(
        monkeypatch,
        lambda request: platform_result(
            request, workflow_version=next(versions), summary=_summary("升版")
        ),
    )

    generate(run_db, user_id)
    generate(run_db, user_id)

    rows = stored(run_db, user_id)
    assert [row["workflow_version"] for row in rows] == [
        WORKFLOW_VERSION,
        "2026-12-01.daily-companion.3",
    ]
    assert rows[-1]["summary"] == _summary("升版")


def test_late_result_does_not_overwrite_newer_report(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(monkeypatch, lambda request: platform_result(request, summary=_summary("新的")))
    generate(run_db, user_id)
    current = stored(run_db, user_id)[0]

    async def persist_late(session: AsyncSession) -> dict[str, Any]:
        row = await service.persist_report(
            session,
            user_id=user_id,
            report_date=DAY,
            started_at=current["updated_at"] - timedelta(hours=1),
            workflow_version=WORKFLOW_VERSION,
            status="ready",
            summary=_summary("迟到的"),
            data_quality={},
            used_record_ids=[],
            input_snapshot_hash="0" * 64,
        )
        return dict(snapshot(row))

    late = run_db(persist_late)

    rows = stored(run_db, user_id)
    assert len(rows) == 1
    assert rows[0]["summary"] == _summary("新的")
    assert late["id"] == rows[0]["id"]


def test_snapshot_hash_changes_with_inputs(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(monkeypatch, lambda request: platform_result(request))

    today = generate(run_db, user_id, DAY)
    same_day = generate(run_db, user_id, DAY)
    next_day = generate(run_db, user_id, DAY + timedelta(days=1))

    assert same_day["input_snapshot_hash"] == today["input_snapshot_hash"]
    # 换一天：手表数据与档案指纹都变，快照哈希必须变
    assert next_day["input_snapshot_hash"] != today["input_snapshot_hash"]
    assert next_day["id"] != today["id"]


def test_snapshot_hash_tracks_archive_changes(
    run_db: RunDb, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_platform(monkeypatch, lambda request: platform_result(request))

    before = generate(run_db, user_id)
    add_episode(run_db, user_id)
    after = generate(run_db, user_id, date(2026, 11, 24))

    assert after["input_snapshot_hash"] != before["input_snapshot_hash"]
