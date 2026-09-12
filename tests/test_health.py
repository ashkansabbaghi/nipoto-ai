from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["env"] == "test"
    assert body["version"]


def test_ready_reports_an_unreachable_db(client: TestClient) -> None:
    """Readiness fails closed: with no database the pod must not take traffic."""
    resp = client.get("/v1/ready")
    assert resp.status_code == 503
    assert resp.json() == {"status": "not_ready", "checks": {"db": "unavailable"}}


def test_health_is_up_even_without_dependencies(client: TestClient) -> None:
    """Liveness must not depend on the DB, or a DB blip restarts every pod (AI-1)."""
    assert client.get("/v1/health").status_code == 200


def test_response_carries_request_id(client: TestClient) -> None:
    resp = client.get("/v1/health")
    assert resp.headers["X-Request-Id"].startswith("req_")


def test_request_id_is_echoed_when_supplied(client: TestClient) -> None:
    resp = client.get("/v1/health", headers={"X-Request-Id": "req_fromcaller"})
    assert resp.headers["X-Request-Id"] == "req_fromcaller"


def test_openapi_is_generated(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert "/v1/health" in spec["paths"]
    assert "/v1/ready" in spec["paths"]


def test_docs_hidden_in_production() -> None:
    app = create_app(Settings(env="production", _env_file=None))  # type: ignore[call-arg]
    with TestClient(app) as c:
        assert c.get("/docs").status_code == 404


def test_cors_allowlist_rejects_unknown_origin(client: TestClient) -> None:
    allowed = client.get("/v1/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"

    other = client.get("/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers
