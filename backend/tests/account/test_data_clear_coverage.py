"""数据管理覆盖：`DELETE /api/data` 与 `DELETE /api/account` 必须清掉每张用户级表。

表清单不手写，从 `Base.metadata` 推导：带 `user_id` 列的表算用户级，经外键挂靠到
它们的子表（答案、幂等键、用药计划、随访记录）一并算。这样新加一张带 `user_id`
的表时用例自动覆盖——D2 的 `daily_report` 漏在 `clear_user_data` 之外时，正是
「清空数据后仍留着日报、注销账号直接外键冲突 500」这个组合暴露出来的。

用例数据全为合成值：只关心「每张表都有一行、清空后为 0 行」，不构造健康信息。
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Table, text
from sqlalchemy import types as sqltypes
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import get_settings
from app.db.base import Base

RunDb = Callable[[Callable[[AsyncSession], Awaitable[Any]]], Any]
Counts = Callable[[list[str]], dict[str, int]]

# 清空数据保留账号，所以账号自身的两行留着：会话与隐私同意属于账号，
# 不属于 api.md 11.3 列出的被清空内容（档案、体征、用药、计划、问诊、随访、提醒）
KEPT_BY_CLEAR = {"consent", "refresh_token"}


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


@pytest.fixture
def counts(test_engine: AsyncEngine) -> Counts:
    def read(names: list[str]) -> dict[str, int]:
        async def query() -> dict[str, int]:
            async with test_engine.connect() as connection:
                result: dict[str, int] = {}
                for name in names:
                    count = await connection.scalar(text(f'SELECT count(*) FROM "{name}"'))
                    result[name] = int(count or 0)
                return result

        return asyncio.run(query())

    return read


def _user_scoped_tables() -> list[Table]:
    """用户级表：有 user_id 的表，加上经外键传递挂靠到它们的子表。"""
    scoped = {table.name for table in Base.metadata.sorted_tables if "user_id" in table.columns}
    changed = True
    while changed:
        changed = False
        for table in Base.metadata.sorted_tables:
            if table.name in scoped:
                continue
            if any(fk.column.table.name in scoped for fk in table.foreign_keys):
                scoped.add(table.name)
                changed = True
    return [table for table in Base.metadata.sorted_tables if table.name in scoped]


def _dummy_value(sqltype: object) -> object:
    if isinstance(sqltype, sqltypes.String):
        return "synth"
    if isinstance(sqltype, sqltypes.DateTime):
        return datetime(2026, 11, 1, 9, 0, 0)
    if isinstance(sqltype, sqltypes.Date):
        return date(2026, 11, 1)
    if isinstance(sqltype, sqltypes.Boolean):
        return False
    if isinstance(sqltype, sqltypes.Integer):
        return 1
    if isinstance(sqltype, sqltypes.JSON):
        return {}
    raise AssertionError(f"未覆盖的列类型: {sqltype}")


async def _seed_every_table(session: AsyncSession, user_id: int) -> dict[str, int]:
    """每张用户级表插一行；子表的父外键直接指向上一步插入的那行。"""
    ids: dict[str, int] = {}
    for table in _user_scoped_tables():
        values: dict[str, object] = {}
        for column in table.columns:
            if column.primary_key or column.nullable:
                continue
            if column.default is not None or column.server_default is not None:
                continue
            parent = next(
                (fk.column.table.name for fk in column.foreign_keys if fk.column.table.name in ids),
                None,
            )
            if column.name == "user_id":
                values[column.name] = user_id
            elif parent is not None:
                values[column.name] = ids[parent]
            else:
                values[column.name] = _dummy_value(column.type)
        inserted = await session.execute(table.insert().values(**values).returning(table.c.id))
        ids[table.name] = int(inserted.scalar_one())
    await session.commit()
    return ids


def test_clear_data_empties_every_user_scoped_table(
    db_client: TestClient, user: dict[str, Any], run_db: RunDb, counts: Counts
) -> None:
    tables = [table.name for table in _user_scoped_tables()]
    run_db(lambda session: _seed_every_table(session, user["user"]["id"]))
    seeded = counts(tables)
    assert all(seeded[name] >= 1 for name in tables), seeded

    cleared = db_client.request(
        "DELETE", "/api/data", json={"confirm": "删除"}, headers=_auth(user)
    )

    assert cleared.status_code == 200, cleared.text
    after = counts(tables + ["user"])
    for name in tables:
        if name in KEPT_BY_CLEAR:
            assert after[name] == seeded[name], name
        else:
            assert after[name] == 0, name
    # 账号保留：user 行还在，会话仍可用
    assert after["user"] == 1
    assert db_client.get("/api/profile", headers=_auth(user)).status_code == 200


def test_delete_account_empties_every_user_scoped_table_and_the_user(
    db_client: TestClient, user: dict[str, Any], run_db: RunDb, counts: Counts
) -> None:
    tables = [table.name for table in _user_scoped_tables()]
    run_db(lambda session: _seed_every_table(session, user["user"]["id"]))
    seeded = counts(tables)
    assert all(seeded[name] >= 1 for name in tables), seeded

    deleted = db_client.request(
        "DELETE", "/api/account", json={"confirm": "删除"}, headers=_auth(user)
    )

    # 漏删任一张用户级表都会在删 user 行时外键冲突，这里同时守住 200 与零残留
    assert deleted.status_code == 200, deleted.text
    assert counts(tables + ["user"]) == dict.fromkeys(tables + ["user"], 0)
    assert (
        db_client.post(
            "/api/auth/login", json={"phone": "13800000001", "password": "passw0rd"}
        ).status_code
        == 401
    )
