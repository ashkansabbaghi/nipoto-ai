"""ORM models for the service's own tables (§13).

AI-2: none of these is a source of truth for conversations, messages or users. We store
only the KB index, audit, feedback, settings and idempotency keys.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, ClassVar

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 1024  # BAAI/bge-m3 (D4)

VISIBILITIES = ("public", "internal")
DOC_TYPES = ("faq", "doc", "internal")
MODES = ("draft", "auto")
REQUEST_STATUSES = ("running", "completed", "failed", "cancelled", "handoff")
VERDICTS = ("accepted", "edited", "rejected", "correct", "wrong", "dangerous")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict] = {
        dict[str, Any]: JSONB,
        list[str]: JSONB,
        Decimal: Numeric(12, 6),
    }


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class KbDocument(Base, TimestampMixin):
    """One FAQ entry or document from the knowledge source (§9.2)."""

    __tablename__ = "kb_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str | None] = mapped_column(String(128))
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunks: Mapped[list[KbChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(f"visibility in {VISIBILITIES}", name="ck_kb_documents_visibility"),
        CheckConstraint(f"type in {DOC_TYPES}", name="ck_kb_documents_type"),
        Index("ix_kb_documents_visibility", "visibility"),
    )


class KbChunk(Base):
    """An embedded slice of a document. `visibility` is denormalised so search filters
    on one table (§9.7)."""

    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False
    )
    visibility: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_norm: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)

    document: Mapped[KbDocument] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "position", name="uq_kb_chunks_document_position"),
        CheckConstraint(f"visibility in {VISIBILITIES}", name="ck_kb_chunks_visibility"),
        Index("ix_kb_chunks_visibility", "visibility"),
    )


class KbGap(Base):
    """A query that found no good source (§9.11)."""

    __tablename__ = "kb_gaps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    search_query: Mapped[str] = mapped_column(Text, nullable=False)
    query_norm: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sample_request_id: Mapped[str | None] = mapped_column(String(64))
    best_score: Mapped[float | None] = mapped_column(Float)


class AiRequest(Base):
    """The audit row for one request (§11.3). Holds personal data: access is restricted
    and a retention period must be decided."""

    __tablename__ = "ai_requests"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    shadow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")

    actor_sub: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(64))
    trigger_message_id: Mapped[str | None] = mapped_column(String(64))

    intent: Mapped[str | None] = mapped_column(String(32))
    search_query: Mapped[str | None] = mapped_column(Text)
    retrieved: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # [{id, score}]
    user_fields_read: Mapped[list[str] | None] = mapped_column(JSONB)  # names only, no values

    prompt_version: Mapped[str | None] = mapped_column(String(32))
    route: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(128))
    output_text: Mapped[str | None] = mapped_column(Text)
    guardrail_actions: Mapped[list[str] | None] = mapped_column(JSONB)
    handoff_reason: Mapped[str | None] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))

    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    ttft_ms: Mapped[int | None] = mapped_column(Integer)
    total_ms: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"mode in {MODES}", name="ck_ai_requests_mode"),
        CheckConstraint(f"status in {REQUEST_STATUSES}", name="ck_ai_requests_status"),
        Index("ix_ai_requests_created_at", "created_at"),
        Index("ix_ai_requests_conversation", "conversation_id"),
        Index("ix_ai_requests_shadow_status", "shadow", "status"),
    )


class ReplyKey(Base):
    """Idempotency for `auto`: one reply per (conversation, trigger message) (§8)."""

    __tablename__ = "reply_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("conversation_id", "trigger_message_id", name="uq_reply_keys_trigger"),
    )


class AiFeedback(Base):
    """Staff or shadow-review verdict on one response."""

    __tablename__ = "ai_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ai_requests.request_id", ondelete="CASCADE"), nullable=False
    )
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    final_text: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    actor_sub: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(f"verdict in {VERDICTS}", name="ck_ai_feedback_verdict"),
        Index("ix_ai_feedback_request", "request_id"),
    )


class Setting(Base):
    """Keys that must change without a deploy — chiefly `auto_mode` (§13)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[str | None] = mapped_column(String(128))


class UsageDaily(Base):
    """Token and cost roll-up per day, route and model (§11.2)."""

    __tablename__ = "usage_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    day: Mapped[datetime] = mapped_column(Date, nullable=False)
    route: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)

    __table_args__ = (UniqueConstraint("day", "route", "model", name="uq_usage_daily_key"),)
