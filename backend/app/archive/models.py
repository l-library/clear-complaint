"""档案域的 ORM 模型：体征、用药、用药计划。

表结构只由 Alembic 迁移创建。体征按 kind 取用对应数值列，其余为 null；
用药状态由业务层维护（expired 由定时任务置位，不在本层）。
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Vital(Base):
    """一次测量。height / weight / bp 三类，各用各的列，其余为 null。"""

    __tablename__ = "vital"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    kind: Mapped[str] = mapped_column(String(8))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 1), default=None)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 1), default=None)
    systolic: Mapped[int | None] = mapped_column(Integer, default=None)
    diastolic: Mapped[int | None] = mapped_column(Integer, default=None)
    pulse: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_vital_user_measured", "user_id", "measured_at"),)


class Medication(Base):
    """一条用药记录。纯文本剂量，服务端不解析不换算（api.md 8.2）。"""

    __tablename__ = "medication"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    dosage_text: Mapped[str | None] = mapped_column(String(40), default=None)
    frequency_text: Mapped[str | None] = mapped_column(String(40), default=None)
    kind: Mapped[str] = mapped_column(String(12))
    started_on: Mapped[date] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(String(12), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_medication_user_kind", "user_id", "kind"),)


class MedicationPlan(Base):
    """用药提醒计划：一天内最多 4 个时刻。"""

    __tablename__ = "medication_plan"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    medication_id: Mapped[int] = mapped_column(
        ForeignKey("medication.id", ondelete="CASCADE"), index=True
    )
    # 时刻升序返回；存 JSONB 保持输入顺序再在服务层排序
    times: Mapped[list[str]] = mapped_column(JSONB)
    started_on: Mapped[date] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(String(12), default="active")
    note: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
