from __future__ import annotations

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import AppError
from app.main import create_app


class Body(BaseModel):
    n: int


@pytest.fixture
def app_with_probes():
    router = APIRouter()

    @router.post("/probe/validate")
    async def _validate(body: Body) -> dict[str, int]:
        return {"n": body.n}

    @router.get("/probe/app-error")
    async def _app_error() -> None:
        raise AppError("no such conversation", code="conversation_not_found", status_code=404)

    @router.get("/probe/boom")
    async def _boom() -> None:
        raise RuntimeError("secret internal detail")

    app = create_app(Settings(env="test", _env_file=None))  # type: ignore[call-arg]
    app.include_router(router, prefix="/v1")
    return app


def test_unknown_path_is_problem_json(client: TestClient) -> None:
    resp = client.get("/v1/nope")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == "not_found"
    assert body["status"] == 404
    assert body["instance"] == "/v1/nope"
    assert body["request_id"].startswith("req_")


def test_app_error_uses_its_code(app_with_probes) -> None:
    with TestClient(app_with_probes) as c:
        resp = c.get("/v1/probe/app-error")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["code"] == "conversation_not_found"


def test_validation_error_is_invalid_request(app_with_probes) -> None:
    with TestClient(app_with_probes) as c:
        resp = c.post("/v1/probe/validate", json={"n": "not-a-number"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "invalid_request"
    assert body["errors"][0]["loc"][-1] == "n"
    # The offending input must not be echoed back (it may hold customer text).
    assert "not-a-number" not in resp.text


def test_unhandled_error_does_not_leak_internals(app_with_probes) -> None:
    with TestClient(app_with_probes, raise_server_exceptions=False) as c:
        resp = c.get("/v1/probe/boom")
    assert resp.status_code == 500
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["code"] == "internal_error"
    assert "secret internal detail" not in resp.text
