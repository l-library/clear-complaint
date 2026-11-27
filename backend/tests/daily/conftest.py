"""日报测试夹具：每例清空相关表，并提供合成用户。

日报没有公开路由，用例直接调 service.generate_daily_report：平台调用在
app.daily.platform.call_daily 打桩，档案与手表数据都由后端自己拼。
"""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.account.models import User

RunDb = Callable[[Callable[[AsyncSession], Awaitable[Any]]], Any]


@pytest.fixture(autouse=True)
def clean_tables(run_db: RunDb) -> None:
    async def truncate(session: AsyncSession) -> None:
        await session.execute(
            text(
                'TRUNCATE "user", profile, episode, episode_answer, daily_report'
                " RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()

    run_db(truncate)


@pytest.fixture
def user_id(run_db: RunDb) -> int:
    async def create(session: AsyncSession) -> int:
        user = User(phone="13800000001", password_hash="synthetic$not-a-real-hash")
        session.add(user)
        await session.commit()
        return user.id

    return int(run_db(create))
