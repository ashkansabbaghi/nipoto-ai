#!/usr/bin/env python3
"""Generate a dev RSA key pair into .keys/ (never used in production).

make keys
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

DEFAULT_DIR = Path(".keys")


def generate(out_dir: Path, *, force: bool = False) -> tuple[Path, Path]:
    private_path = out_dir / "dev_private.pem"
    public_path = out_dir / "dev_public.pem"
    if private_path.exists() and not force:
        print(f"{private_path} already exists; use --force to overwrite.")
        return private_path, public_path

    out_dir.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    private_path.chmod(0o600)
    public_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"wrote {private_path} and {public_path}")
    return private_path, public_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    generate(args.out, force=args.force)


if __name__ == "__main__":
    main()
