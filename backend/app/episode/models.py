"""问诊域的 ORM 模型：问诊、追问回答、幂等键。

表结构只由 Alembic 迁移创建。快照类字段（normalized/env/result/gate）用 JSONB：
它们的形状跟着平台契约走，摊平成列只会把迁移变成字段改名的流水账。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# 问诊状态。expired 不落库：读侧按 expires_at 判定，避免整点扫表改状态
STATUS_CLARIFYING = "clarifying"
STATUS_GENERATING = "generating"
STATUS_READY = "ready"
STATUS_SAVED = "saved"
STATUS_FAILED = "failed"


class Episode(Base):
    """一次问诊。complaint_text 是用户原文，任何环节不改写它。"""

    __tablename__ = "episode"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    status: Mapped[str] = mapped_column(String(16))
    complaint_text: Mapped[str] = mapped_column(String(500))
    city_code: Mapped[str | None] = mapped_column(String(6), default=None)
    # 公开字段名的归一化结果（symptom/onset_at/duration_text/site 等，见 compose.py 的映射表）
    normalized: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    # 自我归因摘除结果：不进入推理链（constraints.md 约束一）
    self_attribution: Mapped[str | None] = mapped_column(String(500), default=None)
    env: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    profile_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    vitals_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    # 本轮证据池：output_list 原样落库，引用下标以它为准
    # output_list 原样落库：列表保序，引用下标以它为准
    evidence_pool: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, default=None)
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    gate: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    # 追问轮次状态：{round, round_limit, skipped, question_fields, missing_fields, questions}
    clarify_state: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # ---- triage request.v2（issue #23）：结果修订与理解状态 ----
    # 结果修订号：首次结果为 0，结果后补充每接受一版 +1；迟到结果按 base_revision 拒收
    revision: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    # 被新版本取代的旧结果，只留最近 RESULT_HISTORY_CAP 版供回看
    result_history: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, default=None)
    # 工作流 understanding 状态：不透明回传对象，后端只校验体积，不解释
    understanding: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    # v2 回答台账：[{answer_id, question_id, action, text}]，原文累计不改写
    raw_answers: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_episode_user_created", "user_id", "created_at"),)


class EpisodeAnswer(Base):
    """一轮追问里用户对单个字段的回答原话，落库不改写。"""

    __tablename__ = "episode_answer"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    episode_id: Mapped[int] = mapped_column(
        ForeignKey("episode.id", ondelete="CASCADE"), index=True
    )
    round: Mapped[int] = mapped_column(BigInteger)
    field: Mapped[str] = mapped_column(String(32))
    value: Mapped[str | None] = mapped_column(String(200), default=None)
    is_unknown: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IdempotencyKey(Base):
    """幂等键到问诊的映射，30 分钟窗口（docs/api.md 1.6）。"""

    __tablename__ = "idempotency_key"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    key: Mapped[str] = mapped_column(String(36))
    episode_id: Mapped[int | None] = mapped_column(
        ForeignKey("episode.id", ondelete="CASCADE"), index=True
    )
    # 请求体指纹：同键不同体是 2006
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("uq_idempotency_user_key", "user_id", "key", unique=True),)
