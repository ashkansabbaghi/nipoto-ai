"""Liveness and readiness (§5.2)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app import __version__
from app.core.logging import get_logger
from app.db.session import get_engine

router = APIRouter(tags=["health"])
log = get_logger("health")


class Health(BaseModel):
    status: str
    env: str
    version: str


class Ready(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/health", response_model=Health, summary="Liveness")
async def health(request: Request) -> Health:
    """Liveness: the process is up. Never touches a dependency (AI-1)."""
    return Health(status="ok", env=request.app.state.settings.env, version=__version__)


async def _check_db() -> str:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        log.warning("readiness_db_failed", error=type(exc).__name__)
        return "unavailable"
    return "ok"


@router.get("/ready", response_model=Ready, summary="Readiness")
async def ready(response: Response) -> Ready:
    checks = {"db": await _check_db()}
    ok = all(value == "ok" for value in checks.values())
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Ready(status="ready" if ok else "not_ready", checks=checks)
