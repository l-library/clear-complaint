"""迁移与测试库连通性。

零迁移时它只证明"库可达、alembic 可跑"；V1 落地后 upgrade head 会在这里
变成对真实建表的回归。CI 的 backend job 带 services: postgres。
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def test_migrated_database_accepts_queries(migrated_db: str) -> None:
    async def check() -> None:
        engine = create_async_engine(migrated_db)
        try:
            async with engine.connect() as connection:
                result = await connection.execute(text("SELECT 1"))
                assert result.scalar() == 1
        finally:
            await engine.dispose()

    asyncio.run(check())
