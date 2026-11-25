"""episode v2 revision and ledgers

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-25 20:05:00.000000

issue #23 的 request.v2 存储层：结果修订号、旧结果回看、工作流
understanding 回传对象、v2 回答台账。既有行取默认值（修订 0、空台账）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "episode", sa.Column("revision", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("episode", sa.Column("result_history", JSONB(), nullable=True))
    op.add_column("episode", sa.Column("understanding", JSONB(), nullable=True))
    op.add_column("episode", sa.Column("raw_answers", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("episode", "raw_answers")
    op.drop_column("episode", "understanding")
    op.drop_column("episode", "result_history")
    op.drop_column("episode", "revision")
