"""The verified caller. Identity comes only from the token (AI-3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

Role = Literal["staff", "user", "guest", "service", "admin"]
ROLES: tuple[str, ...] = get_args(Role)


@dataclass(frozen=True, slots=True)
class Actor:
    """A caller whose JWT has been verified.

    `user_id` is the token's `sub`. It is never read from a request body and never
    taken from model output.
    """

    user_id: str
    role: Role
    token_id: str | None = None
    expires_at: int | None = None

    @property
    def is_staff_side(self) -> bool:
        """Staff-side actors may see `internal` knowledge (§9.2)."""
        return self.role in ("staff", "admin", "service")

    @property
    def is_guest(self) -> bool:
        return self.role == "guest"
