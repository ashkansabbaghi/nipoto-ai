"""T1.2: JWT verification and the §6.3 role matrix."""

from __future__ import annotations

import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.actor import Actor
from app.core.auth import CurrentActor, require_roles
from app.core.config import Settings
from app.main import create_app
from scripts.mint_token import mint

AUDIENCE = "nipoto-ai"


def _pem_pair(tmp_path: Path) -> tuple[str, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_path = tmp_path / "pub.pem"
    public_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_pem, public_path


@pytest.fixture
def keys(tmp_path: Path) -> tuple[str, Path]:
    return _pem_pair(tmp_path)


@pytest.fixture
def other_private_key(tmp_path: Path) -> str:
    other = tmp_path / "other"
    other.mkdir()
    private_pem, _ = _pem_pair(other)
    return private_pem


@pytest.fixture
def auth_app(keys: tuple[str, Path]) -> FastAPI:
    _, public_path = keys
    settings = Settings(
        env="test",
        jwt_audience=AUDIENCE,
        jwt_public_key_file=str(public_path),
        jwks_url=None,
        _env_file=None,  # type: ignore[call-arg]
    )
    router = APIRouter()

    @router.get("/probe/any")
    async def _any(actor: CurrentActor) -> dict[str, str]:
        return {"user_id": actor.user_id, "role": actor.role}

    @router.get("/probe/search", dependencies=[Depends(require_roles("staff", "admin", "service"))])
    async def _search() -> dict[str, bool]:
        return {"ok": True}

    @router.get("/probe/admin", dependencies=[Depends(require_roles("admin"))])
    async def _admin() -> dict[str, bool]:
        return {"ok": True}

    app = create_app(settings)
    app.include_router(router, prefix="/v1")
    return app


def token(private_key: str, *, role: str = "staff", sub: str = "u1", ttl: int = 600, **over) -> str:
    kwargs = {"audience": AUDIENCE, **over}
    return mint(role=role, sub=sub, ttl_seconds=ttl, private_key=private_key, **kwargs)


def auth(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def test_valid_token_yields_actor(auth_app: FastAPI, keys) -> None:
    private_key, _ = keys
    with TestClient(auth_app) as c:
        resp = c.get("/v1/probe/any", headers=auth(token(private_key, role="staff", sub="u42")))
    assert resp.status_code == 200
    assert resp.json() == {"user_id": "u42", "role": "staff"}


def test_missing_token_is_401(auth_app: FastAPI) -> None:
    with TestClient(auth_app) as c:
        resp = c.get("/v1/probe/any")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["code"] == "unauthenticated"


def test_non_bearer_scheme_is_401(auth_app: FastAPI, keys) -> None:
    private_key, _ = keys
    with TestClient(auth_app) as c:
        resp = c.get("/v1/probe/any", headers={"Authorization": f"Basic {token(private_key)}"})
    assert resp.status_code == 401


def test_wrong_signature_is_401(auth_app: FastAPI, other_private_key: str) -> None:
    with TestClient(auth_app) as c:
        resp = c.get("/v1/probe/any", headers=auth(token(other_private_key)))
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_token"


def test_expired_token_is_401(auth_app: FastAPI, keys) -> None:
    private_key, _ = keys
    expired = mint(
        role="staff",
        sub="u1",
        ttl_seconds=60,
        private_key=private_key,
        audience=AUDIENCE,
        issued_at=int(time.time()) - 3600,
    )
    with TestClient(auth_app) as c:
        resp = c.get("/v1/probe/any", headers=auth(expired))
    assert resp.status_code == 401
    assert resp.json()["code"] == "token_expired"


def test_wrong_audience_is_401(auth_app: FastAPI, keys) -> None:
    private_key, _ = keys
    with TestClient(auth_app) as c:
        resp = c.get("/v1/probe/any", headers=auth(token(private_key, audience="other-service")))
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_token"


def test_unknown_role_is_401(auth_app: FastAPI, keys) -> None:
    private_key, _ = keys
    tok = jwt.encode(
        {
            "sub": "u1",
            "role": "superuser",
            "aud": AUDIENCE,
            "exp": int(time.time()) + 600,
        },
        private_key,
        algorithm="RS256",
    )
    with TestClient(auth_app) as c:
        resp = c.get("/v1/probe/any", headers=auth(tok))
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_token"


def test_token_without_sub_is_401(auth_app: FastAPI, keys) -> None:
    private_key, _ = keys
    tok = jwt.encode(
        {"role": "staff", "aud": AUDIENCE, "exp": int(time.time()) + 600},
        private_key,
        algorithm="RS256",
    )
    with TestClient(auth_app) as c:
        resp = c.get("/v1/probe/any", headers=auth(tok))
    assert resp.status_code == 401


def test_unsigned_token_is_rejected(auth_app: FastAPI) -> None:
    """An `alg: none` token must never be accepted."""
    tok = jwt.encode(
        {"sub": "u1", "role": "admin", "aud": AUDIENCE, "exp": int(time.time()) + 600},
        key="",
        algorithm="none",
    )
    with TestClient(auth_app) as c:
        resp = c.get("/v1/probe/any", headers=auth(tok))
    assert resp.status_code == 401


@pytest.mark.parametrize(
    ("role", "expected"),
    [("staff", 200), ("admin", 200), ("service", 200), ("user", 403), ("guest", 403)],
)
def test_search_role_matrix(auth_app: FastAPI, keys, role: str, expected: int) -> None:
    private_key, _ = keys
    with TestClient(auth_app) as c:
        resp = c.get("/v1/probe/search", headers=auth(token(private_key, role=role)))
    assert resp.status_code == expected
    if expected == 403:
        assert resp.json()["code"] == "forbidden"
        assert resp.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize(
    ("role", "expected"),
    [("admin", 200), ("staff", 403), ("service", 403), ("user", 403), ("guest", 403)],
)
def test_admin_role_matrix(auth_app: FastAPI, keys, role: str, expected: int) -> None:
    private_key, _ = keys
    with TestClient(auth_app) as c:
        resp = c.get("/v1/probe/admin", headers=auth(token(private_key, role=role)))
    assert resp.status_code == expected


def test_require_roles_rejects_unknown_role_at_import_time() -> None:
    with pytest.raises(ValueError, match="Unknown role"):
        require_roles("superuser")  # type: ignore[arg-type]


def test_actor_visibility_flags() -> None:
    assert Actor(user_id="u1", role="staff").is_staff_side
    assert Actor(user_id="u1", role="admin").is_staff_side
    assert Actor(user_id="u1", role="service").is_staff_side
    assert not Actor(user_id="u1", role="user").is_staff_side
    assert not Actor(user_id="u1", role="guest").is_staff_side
    assert Actor(user_id="g1", role="guest").is_guest


def test_missing_auth_config_is_not_a_silent_pass(keys) -> None:
    """With neither a public key nor JWKS, requests fail closed (500), never 200."""
    private_key, _ = keys
    settings = Settings(
        env="test",
        jwt_audience=AUDIENCE,
        jwt_public_key_file=None,
        jwks_url=None,
        _env_file=None,  # type: ignore[call-arg]
    )
    router = APIRouter()

    @router.get("/probe/any")
    async def _any(actor: CurrentActor) -> dict[str, str]:
        return {"user_id": actor.user_id}

    app = create_app(settings)
    app.include_router(router, prefix="/v1")
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/v1/probe/any", headers=auth(token(private_key)))
    assert resp.status_code == 500
    assert resp.json()["code"] == "internal_error"


def test_jwks_url_takes_precedence(monkeypatch, keys, tmp_path: Path) -> None:
    """When JWKS_URL is set, the key comes from the JWKS client, not the PEM file."""
    private_key, _ = keys
    unrelated_dir = tmp_path / "unrelated"
    unrelated_dir.mkdir()
    unrelated_private, unrelated_public = _pem_pair(unrelated_dir)

    class FakeSigningKey:
        key = unrelated_public.read_text(encoding="utf-8")

    class FakeJWKClient:
        def __init__(self, *args, **kwargs) -> None: ...

        def get_signing_key_from_jwt(self, _token: str) -> FakeSigningKey:
            return FakeSigningKey()

    monkeypatch.setattr("app.core.auth.PyJWKClient", FakeJWKClient)
    from app.core.auth import _jwk_client

    _jwk_client.cache_clear()

    settings = Settings(
        env="test",
        jwt_audience=AUDIENCE,
        jwt_public_key_file="does-not-exist.pem",
        jwks_url="https://backend.example/.well-known/jwks.json",
        _env_file=None,  # type: ignore[call-arg]
    )
    router = APIRouter()

    @router.get("/probe/any")
    async def _any(actor: CurrentActor) -> dict[str, str]:
        return {"user_id": actor.user_id}

    app = create_app(settings)
    app.include_router(router, prefix="/v1")
    with TestClient(app) as c:
        # Signed by the JWKS key -> accepted; signed by the PEM-file key -> rejected.
        assert c.get("/v1/probe/any", headers=auth(token(unrelated_private))).status_code == 200
        assert c.get("/v1/probe/any", headers=auth(token(private_key))).status_code == 401
    _jwk_client.cache_clear()
