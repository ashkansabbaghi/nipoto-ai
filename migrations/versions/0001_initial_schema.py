"""initial schema (§13)

Revision ID: 0001
Revises:
Create Date: 2026-09-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024  # BAAI/bge-m3 (D4)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "kb_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source_id", sa.String(128)),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("visibility in ('public', 'internal')", name="ck_kb_documents_visibility"),
        sa.CheckConstraint("type in ('faq', 'doc', 'internal')", name="ck_kb_documents_type"),
    )
    op.create_index("ix_kb_documents_visibility", "kb_documents", ["visibility"])

    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.String(64),
            sa.ForeignKey("kb_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("visibility", sa.String(16), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("text_norm", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("embedding_model", sa.String(128), nullable=False),
        sa.Column("token_count", sa.Integer),
        sa.UniqueConstraint("document_id", "position", name="uq_kb_chunks_document_position"),
        sa.CheckConstraint("visibility in ('public', 'internal')", name="ck_kb_chunks_visibility"),
    )
    op.create_index("ix_kb_chunks_visibility", "kb_chunks", ["visibility"])
    # HNSW over cosine distance: vectors are normalised, and the KB is small enough that
    # build time is negligible (§9.7).
    op.execute(
        "CREATE INDEX ix_kb_chunks_embedding ON kb_chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )

    op.create_table(
        "kb_gaps",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("search_query", sa.Text, nullable=False),
        sa.Column("query_norm", sa.Text, nullable=False, unique=True),
        sa.Column("count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sample_request_id", sa.String(64)),
        sa.Column("best_score", sa.Float),
    )

    op.create_table(
        "ai_requests",
        sa.Column("request_id", sa.String(64), primary_key=True),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("shadow", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("actor_sub", sa.String(128), nullable=False),
        sa.Column("actor_role", sa.String(16), nullable=False),
        sa.Column("conversation_id", sa.String(64)),
        sa.Column("trigger_message_id", sa.String(64)),
        sa.Column("intent", sa.String(32)),
        sa.Column("search_query", sa.Text),
        sa.Column("retrieved", postgresql.JSONB),
        sa.Column("user_fields_read", postgresql.JSONB),
        sa.Column("prompt_version", sa.String(32)),
        sa.Column("route", sa.String(32)),
        sa.Column("model", sa.String(128)),
        sa.Column("output_text", sa.Text),
        sa.Column("guardrail_actions", postgresql.JSONB),
        sa.Column("handoff_reason", sa.String(32)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("tokens_in", sa.Integer),
        sa.Column("tokens_out", sa.Integer),
        sa.Column("ttft_ms", sa.Integer),
        sa.Column("total_ms", sa.Integer),
        sa.Column("cost_usd", sa.Numeric(12, 6)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("mode in ('draft', 'auto')", name="ck_ai_requests_mode"),
        sa.CheckConstraint(
            "status in ('running', 'completed', 'failed', 'cancelled', 'handoff')",
            name="ck_ai_requests_status",
        ),
    )
    op.create_index("ix_ai_requests_created_at", "ai_requests", ["created_at"])
    op.create_index("ix_ai_requests_conversation", "ai_requests", ["conversation_id"])
    op.create_index("ix_ai_requests_shadow_status", "ai_requests", ["shadow", "status"])

    op.create_table(
        "reply_keys",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("trigger_message_id", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("conversation_id", "trigger_message_id", name="uq_reply_keys_trigger"),
    )

    op.create_table(
        "ai_feedback",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "request_id",
            sa.String(64),
            sa.ForeignKey("ai_requests.request_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("final_text", sa.Text),
        sa.Column("comment", sa.Text),
        sa.Column("actor_sub", sa.String(128), nullable=False),
        sa.Column("actor_role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "verdict in ('accepted', 'edited', 'rejected', 'correct', 'wrong', 'dangerous')",
            name="ck_ai_feedback_verdict",
        ),
    )
    op.create_index("ix_ai_feedback_request", "ai_feedback", ["request_id"])

    op.create_table(
        "settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", postgresql.JSONB, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.String(128)),
    )
    # D9: only `off` and `shadow` are implemented in the MVP; the default is `shadow`.
    op.execute("INSERT INTO settings (key, value) VALUES ('auto_mode', '\"shadow\"'::jsonb)")

    op.create_table(
        "usage_daily",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("route", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("requests", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.UniqueConstraint("day", "route", "model", name="uq_usage_daily_key"),
    )


def downgrade() -> None:
    op.drop_table("usage_daily")
    op.drop_table("settings")
    op.drop_index("ix_ai_feedback_request", table_name="ai_feedback")
    op.drop_table("ai_feedback")
    op.drop_table("reply_keys")
    op.drop_index("ix_ai_requests_shadow_status", table_name="ai_requests")
    op.drop_index("ix_ai_requests_conversation", table_name="ai_requests")
    op.drop_index("ix_ai_requests_created_at", table_name="ai_requests")
    op.drop_table("ai_requests")
    op.drop_table("kb_gaps")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_embedding")
    op.drop_index("ix_kb_chunks_visibility", table_name="kb_chunks")
    op.drop_table("kb_chunks")
    op.drop_index("ix_kb_documents_visibility", table_name="kb_documents")
    op.drop_table("kb_documents")
