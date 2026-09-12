"""Runtime settings that change without a deploy (§13).

The important one is `auto_mode`, the kill switch for the `auto` mode. It is read on the
request path, so it is cached briefly — a change in the DB takes effect within
`SETTINGS_TTL_SECONDS`, with no restart.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.models import Setting
from app.db.session import session_scope

log = get_logger("settings")

SETTINGS_TTL_SECONDS = 10.0

AUTO_MODE = "auto_mode"
AUTO_MODES = ("off", "shadow", "live")
DEFAULTS: dict[str, Any] = {AUTO_MODE: "shadow"}

_cache: dict[str, tuple[float, Any]] = {}


class NotImplementedSetting(AppError):
    status_code = 501
    code = "not_implemented"
    title = "Not Implemented"


def clear_cache() -> None:
    _cache.clear()


async def get(key: str, default: Any = None) -> Any:
    """Read a setting, cached for a few seconds.

    If the DB is unreachable the built-in default is used: a database blip must not take
    the service down, and the default (`shadow`) is the safe direction.
    """
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and cached[0] > now:
        return cached[1]

    fallback = DEFAULTS.get(key, default)
    try:
        async with session_scope() as session:
            row = await session.scalar(select(Setting).where(Setting.key == key))
        value = row.value if row is not None else fallback
    except Exception as exc:
        log.warning("settings_read_failed", key=key, error=type(exc).__name__)
        return fallback

    _cache[key] = (now + SETTINGS_TTL_SECONDS, value)
    return value


async def set(key: str, value: Any, *, actor_sub: str | None = None) -> None:
    async with session_scope() as session:
        stmt = (
            insert(Setting)
            .values(key=key, value=value, updated_by=actor_sub)
            .on_conflict_do_update(
                index_elements=[Setting.key],
                set_={"value": value, "updated_by": actor_sub},
            )
        )
        await session.execute(stmt)
    _cache.pop(key, None)


async def auto_mode() -> str:
    """`off` | `shadow` (D9: `live` is rejected where it is acted on)."""
    value = await get(AUTO_MODE)
    if value not in AUTO_MODES:
        log.warning("settings_invalid_auto_mode", value=value)
        return DEFAULTS[AUTO_MODE]
    return value
