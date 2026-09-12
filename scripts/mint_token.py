#!/usr/bin/env python3
"""Mint a dev JWT signed with the local dev key.

make token ROLE=staff SUB=u1
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

import jwt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.actor import ROLES
from app.core.config import get_settings


def mint(
    *,
    role: str,
    sub: str,
    ttl_seconds: int,
    private_key: str,
    audience: str,
    issued_at: int | None = None,
) -> str:
    now = issued_at if issued_at is not None else int(time.time())
    claims = {
        "sub": sub,
        "role": role,
        "aud": audience,
        "iss": "nipoto-dev",
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, private_key, algorithm="RS256")


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", default="staff", choices=ROLES)
    parser.add_argument("--sub", default="u1")
    parser.add_argument("--ttl", type=int, default=600, help="seconds (default 600, as in §6.2)")
    parser.add_argument("--key", type=Path, default=None)
    args = parser.parse_args()

    key_path = args.key or Path(settings.jwt_private_key_file or ".keys/dev_private.pem")
    if not key_path.is_file():
        raise SystemExit(f"{key_path} not found. Run `make keys` first.")

    print(
        mint(
            role=args.role,
            sub=args.sub,
            ttl_seconds=args.ttl,
            private_key=key_path.read_text(encoding="utf-8"),
            audience=settings.jwt_audience,
        )
    )


if __name__ == "__main__":
    main()
