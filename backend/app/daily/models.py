"""每日健康关怀域的 ORM 模型：当日报告。

表结构只由 Alembic 迁移创建。一行代表「某用户某天某个工作流版本」的当前报告：
同版本重算按更新覆盖，平台升版后同日各留一行，读侧取 updated_at 最新的一份
（docs/api-agentarts.md 16.8.8 第 6 条）。
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyReport(Base):
    __tablename__ = "daily_report"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    report_date: Mapped[date] = mapped_column(Date)
    # 平台回显的 DSL 版本，不在客户端写死断言；空串表示未调用平台（本地待核实短路）
    workflow_version: Mapped[str] = mapped_column(String(64), server_default="")
    # "mock" 或 "device"；16.8.2 的请求取值，模拟标记全链路保留
    data_source: Mapped[str] = mapped_column(String(8))
    # 平台内部 status：ready/degraded/data_insufficient/review_required
    status: Mapped[str] = mapped_column(String(24))
    # 内部 status 为 review_required 且本地短路时没有小结正文，故允许 null
    summary: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    data_quality: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    used_record_ids: Mapped[list[str] | None] = mapped_column(JSONB, default=None)
    # 输入快照哈希：覆盖 watch_data/health_archive/safety_context，不含 request_id
    input_snapshot_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "report_date", "workflow_version", name="uq_daily_report_user_date_version"
        ),
    )
