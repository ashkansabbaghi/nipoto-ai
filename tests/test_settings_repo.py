"""T1.4: the runtime `settings` table and its short-lived cache."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.db import session as db_session
from app.db.repositories import settings as repo


@pytest.fixture(autouse=True)
def _clean_cache():
    repo.clear_cache()
    yield
    repo.clear_cache()


async def test_falls_back_to_the_default_when_the_db_is_down() -> None:
    """A DB blip must not take `auto` down; `shadow` is the safe direction (D9)."""
    assert await repo.auto_mode() == "shadow"


async def test_unknown_key_returns_the_supplied_default() -> None:
    assert await repo.get("no_such_key", default="x") == "x"


async def test_an_invalid_stored_value_falls_back(monkeypatch) -> None:
    async def fake_get(key: str, default=None):
        return "live-ish-typo"

    monkeypatch.setattr(repo, "get", fake_get)
    assert await repo.auto_mode() == "shadow"


@pytest.mark.db
async def test_change_in_db_applies_without_a_restart(db_url: str) -> None:
    db_session.init_engine(Settings(env="test", database_url=db_url, _env_file=None))  # type: ignore[call-arg]
    try:
        await repo.set(repo.AUTO_MODE, "shadow")
        assert await repo.auto_mode() == "shadow"

        # `set` invalidates the cache, so the new value is visible immediately.
        await repo.set(repo.AUTO_MODE, "off", actor_sub="admin1")
        assert await repo.auto_mode() == "off"

        # A write from elsewhere is picked up once the short TTL expires.
        repo.clear_cache()
        assert await repo.auto_mode() == "off"

        await repo.set(repo.AUTO_MODE, "shadow")
    finally:
        await db_session.dispose_engine()


async def test_cache_ttl_is_short_enough_to_be_a_kill_switch() -> None:
    assert repo.SETTINGS_TTL_SECONDS <= 30
