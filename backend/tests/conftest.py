"""测试夹具。

数据库夹具要求本地 docker compose 的 Postgres 在跑。表结构只经 Alembic 迁移创建，
测试库每个会话重建一次，跑测试不会碰开发库 clear_complaint 的数据。
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]

# CI 用环境变量指到 services 起的实例；本地默认就是 docker-compose.yml 里那个
DEFAULT_TEST_URL = (
    "postgresql+asyncpg://clear_complaint:clear_complaint@localhost:5432/clear_complaint_test"
)


def test_database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)


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
