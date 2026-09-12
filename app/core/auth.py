"""JWT verification and role-based authorization (§6).

The service verifies signatures locally: no call to the main backend per request (AI-1).
Dev uses an RS256 public key file; production uses the backend's JWKS endpoint.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request, status
from jwt import PyJWKClient

from app.core.actor import ROLES, Actor, Role
from app.core.config import Settings, get_settings
from app.core.errors import AppError

ALGORITHMS = ["RS256"]


class Unauthenticated(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"
    title = "Unauthenticated"


class Forbidden(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    title = "Forbidden"


class AuthConfigError(RuntimeError):
    """Neither a public key nor a JWKS URL is configured."""


@lru_cache(maxsize=4)
def _jwk_client(jwks_url: str) -> PyJWKClient:
    # PyJWKClient caches keys itself, so the JWKS endpoint is not hit per request.
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)


def _signing_key(token: str, settings: Settings) -> Any:
    if settings.jwks_url:
        return _jwk_client(settings.jwks_url).get_signing_key_from_jwt(token).key
    if settings.jwt_public_key_file:
        path = Path(settings.jwt_public_key_file)
        if not path.is_file():
            raise AuthConfigError(f"JWT_PUBLIC_KEY_FILE not found: {path}")
        return path.read_text(encoding="utf-8")
    raise AuthConfigError("Set either JWKS_URL or JWT_PUBLIC_KEY_FILE.")


def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        key = _signing_key(token, settings)
    except AuthConfigError:
        raise
    except Exception as exc:  # unknown kid, unreachable JWKS, malformed token
        raise Unauthenticated("Token key could not be resolved.", code="invalid_token") from exc

    try:
        return jwt.decode(
            token,
            key,
            algorithms=ALGORITHMS,
            audience=settings.jwt_audience,
            options={"require": ["exp", "sub", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise Unauthenticated("Token has expired.", code="token_expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise Unauthenticated("Token audience is not this service.", code="invalid_token") from exc
    except jwt.InvalidTokenError as exc:
        raise Unauthenticated("Token is invalid.", code="invalid_token") from exc


def actor_from_claims(claims: dict[str, Any]) -> Actor:
    role = claims.get("role")
    if role not in ROLES:
        raise Unauthenticated("Token carries no known role.", code="invalid_token")
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise Unauthenticated("Token carries no subject.", code="invalid_token")
    return Actor(
        user_id=sub,
        role=role,  # type: ignore[arg-type]
        token_id=claims.get("jti"),
        expires_at=claims.get("exp"),
    )


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header:
        raise Unauthenticated("Authorization header is missing.", code="unauthenticated")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise Unauthenticated("Expected 'Authorization: Bearer <jwt>'.", code="unauthenticated")
    return token.strip()


async def current_actor(request: Request) -> Actor:
    """FastAPI dependency: the verified caller."""
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    actor = actor_from_claims(decode_token(_bearer_token(request), settings))
    request.state.actor = actor
    return actor


CurrentActor = Annotated[Actor, Depends(current_actor)]


def require_roles(*roles: Role) -> Callable[..., Any]:
    """Dependency factory enforcing the role matrix of §6.3."""
    allowed = frozenset(roles)
    if not allowed <= frozenset(ROLES):
        raise ValueError(f"Unknown role in {roles!r}")

    async def dependency(actor: CurrentActor) -> Actor:
        if actor.role not in allowed:
            raise Forbidden(f"Role '{actor.role}' may not use this endpoint.")
        return actor

    return dependency
