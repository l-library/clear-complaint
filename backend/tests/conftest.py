"""测试夹具。

数据库夹具要求本地 docker compose 的 Postgres 在跑。表结构只经 Alembic 迁移创建，
测试库每个会话重建一次，跑测试不会碰开发库 clear_complaint 的数据。
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from typing import TypeVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import get_session
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parents[1]

# CI 用环境变量指到 services 起的实例；本地默认就是 docker-compose.yml 里那个
DEFAULT_TEST_URL = (
    "postgresql+asyncpg://clear_complaint:clear_complaint@localhost:5432/clear_complaint_test"
)


def test_database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)


@pytest.fixture
def export_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """导出目录指到临时目录。

    `DELETE /api/data` 与 `DELETE /api/account` 会顺带清导出文件，未配置
    EXPORT_DIR 时那条路径直接报错；CI 没有 .env，所以凡是要走这两个接口的用例
    都必须领这个 fixture，否则本地（有 .env）绿、CI 红。
    """
    directory = tmp_path / "exports"
    monkeypatch.setattr(get_settings(), "export_dir", str(directory))
    return directory


async def _recreate_database(url: str) -> None:
    target = make_url(url)
    admin = create_async_engine(target.set(database="postgres"))
    try:
        async with admin.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{target.database}"'))
            await connection.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        await admin.dispose()


@pytest.fixture(scope="session")
def migrated_db() -> Iterator[str]:
    """一个干净的测试库：先重建，再跑 alembic upgrade head。返回连接串。"""
    url = test_database_url()
    try:
        asyncio.run(_recreate_database(url))
    except SQLAlchemyError as exc:
        pytest.fail(f"测试库连不上（先 docker compose up -d）：{exc}", pytrace=False)
    # env.py 从环境读连接串；环境变量优先于 .env，正好把迁移指到测试库
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
        env={**os.environ, "DATABASE_URL": url},
    )
    yield url


@pytest.fixture(scope="session")
def test_engine(migrated_db: str) -> Iterator[AsyncEngine]:
    # NullPool：连接即用即关，避免连接绑死在某个事件循环上（夹具与 TestClient 各自持有循环）
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    yield engine
    asyncio.run(engine.dispose())


async def _truncate(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                'TRUNCATE "user", consent, refresh_token, profile,'
                " episode, episode_answer, idempotency_key, reminder,"
                " followup_record, vital, medication, medication_plan, daily_report"
                " RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def db_client(test_engine: AsyncEngine) -> Iterator[TestClient]:
    """带真实数据库会话的客户端，每个用例先清空账号三张表。"""
    asyncio.run(_truncate(test_engine))
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def db_execute(test_engine: AsyncEngine) -> Callable[[str], None]:
    """直改测试库数据的口子：过期、改状态这类用例不想绕业务接口。"""

    def run(sql: str) -> None:
        async def _run() -> None:
            async with test_engine.begin() as connection:
                await connection.execute(text(sql))

        asyncio.run(_run())

    return run


_T = TypeVar("_T")


@pytest.fixture
def run_db(test_engine: AsyncEngine) -> Callable[[Callable[[AsyncSession], Awaitable[_T]]], _T]:
    """在独立会话与事件循环里执行一次数据库操作，返回结果。

    每次调用全新会话：asyncpg 连接绑死创建它的事件循环，跨循环复用会话必炸。
    """
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    def run(operation: Callable[[AsyncSession], Awaitable[_T]]) -> _T:

        async def wrapper() -> _T:
            async with factory() as session:
                return await operation(session)

        return asyncio.run(wrapper())

    return run
