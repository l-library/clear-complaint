"""daily report table

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-28 10:20:00.000000

每日健康关怀的当日报告（docs/daily-companion.md 第 3 节）：唯一键
(user_id, report_date, workflow_version) 保证一个用户一天一个当前版本，
同版本重算按更新覆盖，平台升版后同日各留一行。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_report",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("workflow_version", sa.String(length=64), server_default="", nullable=False),
        sa.Column("data_source", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("summary", JSONB(), nullable=True),
        sa.Column("data_quality", JSONB(), nullable=True),
        sa.Column("used_record_ids", JSONB(), nullable=True),
        sa.Column("input_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_daily_report_user_id"),
        sa.PrimaryKeyConstraint("id", name="pk_daily_report"),
        sa.UniqueConstraint(
            "user_id",
            "report_date",
            "workflow_version",
            name="uq_daily_report_user_date_version",
        ),
    )
    op.create_index("ix_daily_report_user_id", "daily_report", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_daily_report_user_id", table_name="daily_report")
    op.drop_table("daily_report")
