"""提醒域。M4 只落表与问诊保存时的创建；列表与响应端点在 M6。"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

KIND_FOLLOWUP = "followup"
KIND_RECHECK = "recheck"
KIND_MEDICATION = "medication"

STATUS_PENDING = "pending"
STATUS_DONE = "done"
STATUS_SKIPPED = "skipped"
STATUS_MISSED = "missed"
STATUS_EXPIRED = "expired"


class Reminder(Base):
    """站内提醒：followup / recheck 由问诊保存时创建。文案由后端模板拼装。"""

    __tablename__ = "reminder"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    episode_id: Mapped[int | None] = mapped_column(
        ForeignKey("episode.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(12), default=STATUS_PENDING)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(String(100))
    body: Mapped[str | None] = mapped_column(String(200), default=None)
    snooze_count: Mapped[int] = mapped_column(BigInteger, default=0)
    # 定时任务生成用药提醒的防重键（med:{plan}:{date}:{time}），手工提醒为 null
    dedupe_key: Mapped[str | None] = mapped_column(String(120), default=None, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FollowupRecord(Base):
    """一次随访回答的完整记录：第一层规则结论 + 第二层补充（可能降级为空）。"""

    __tablename__ = "followup_record"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    reminder_id: Mapped[int] = mapped_column(
        ForeignKey("reminder.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[int | None] = mapped_column(
        ForeignKey("episode.id", ondelete="CASCADE"), index=True
    )
    answers: Mapped[dict[str, object]] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(String(200), default=None)
    advice_level: Mapped[str] = mapped_column(String(16))
    advice_text: Mapped[str] = mapped_column(String(100))
    supplement: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
