"""T1.3: schema and migrations. These need Postgres and skip when it is unreachable."""

from __future__ import annotations

import asyncio
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.db.models import EMBEDDING_DIM, Base

pytestmark = pytest.mark.db

EXPECTED_TABLES = {
    "kb_documents",
    "kb_chunks",
    "kb_gaps",
    "ai_requests",
    "reply_keys",
    "ai_feedback",
    "settings",
    "usage_daily",
}


def test_models_cover_every_table_of_section_13() -> None:
    """Pure metadata check: no database needed."""
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_chunk_vector_dimension_matches_bge_m3() -> None:
    column = Base.metadata.tables["kb_chunks"].c.embedding
    assert EMBEDDING_DIM == 1024
    assert column.type.dim == EMBEDDING_DIM


def test_reply_keys_is_unique_on_the_idempotency_pair() -> None:
    """The `auto` idempotency guarantee rests on this constraint (§8)."""
    table = Base.metadata.tables["reply_keys"]
    pairs = {
        tuple(sorted(c.name for c in constraint.columns))
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("conversation_id", "trigger_message_id") in pairs


def test_ai_requests_has_the_shadow_column() -> None:
    assert "shadow" in Base.metadata.tables["ai_requests"].c


def test_migrations_create_every_table(db_url: str) -> None:
    """`alembic upgrade head` on an empty database produces the §13 schema."""
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        capture_output=True,
    )
    asyncio.run(_assert_schema(db_url))


async def _assert_schema(db_url: str) -> None:
    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            tables = {row[0] for row in rows}
            assert EXPECTED_TABLES <= tables

            # The vector extension and the HNSW index must exist, or search falls back
            # to a sequential scan without anyone noticing.
            ext = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            assert ext.first() is not None
            idx = await conn.execute(
                text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_kb_chunks_embedding'")
            )
            assert idx.first() is not None

            mode = await conn.execute(text("SELECT value FROM settings WHERE key = 'auto_mode'"))
            assert mode.scalar() == "shadow"  # D9 default
    finally:
        await engine.dispose()


async def test_ready_is_200_with_a_live_db(db_url: str) -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(Settings(env="test", database_url=db_url, _env_file=None))  # type: ignore[call-arg]
    with TestClient(app) as client:
        resp = client.get("/v1/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"]["db"] == "ok"
