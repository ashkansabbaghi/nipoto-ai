from __future__ import annotations

import asyncio
import socket
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env="test",
        cors_origins=["http://localhost:5173"],
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    with TestClient(create_app(settings)) as c:
        yield c


def _postgres_is_reachable(url: str) -> bool:
    parsed = urlparse(url.replace("postgresql+asyncpg://", "postgresql://"))
    host, port = parsed.hostname or "localhost", parsed.port or 5432
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def db_url() -> str:
    """The test database URL, or skip. Tests using it are marked `db`."""
    url = Settings().database_url
    if not _postgres_is_reachable(url):
        pytest.skip(f"Postgres is not reachable at {url}")
    return url


@pytest.fixture(autouse=True)
def _reset_db_engine():
    """Each app instance gets a fresh engine; module-level state must not leak."""
    yield
    from app.db import session

    if session._engine is not None:
        asyncio.run(session.dispose_engine())
