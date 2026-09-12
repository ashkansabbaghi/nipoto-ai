"""The only place in the codebase that knows about the main backend (AI-1).

Domain models here are ours, not the backend's wire format: the HTTP implementation maps
camelCase fields onto them, so the rest of the app never sees the backend's shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from app.core.actor import Actor
from app.core.errors import AppError


class HandledBy(StrEnum):
    ASSISTANT = "assistant"
    STAFF = "staff"


class AuthorKind(StrEnum):
    USER = "user"  # also covers guests
    STAFF = "staff"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationStatus(StrEnum):
    QUEUED = "queued"
    OPENED = "opened"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class Conversation:
    id: str
    owner_id: str
    status: ConversationStatus
    handled_by: HandledBy
    department_id: str | None = None
    staff_id: str | None = None
    title: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_handled_by_assistant(self) -> bool:
        return self.handled_by is HandledBy.ASSISTANT


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    author_kind: AuthorKind
    text: str
    sent_at: datetime | None = None
    author_id: str | None = None
    conversation_id: str | None = None
    has_attachment: bool = False


@dataclass(frozen=True, slots=True)
class KbItem:
    id: str
    type: str
    visibility: str
    title: str = ""
    body: str = ""
    url: str | None = None
    updated_at: datetime | None = None
    deleted: bool = False


@dataclass(frozen=True, slots=True)
class OrderSummary:
    """Allowlisted fields only (§7.1); dates arrive pre-formatted in Jalali."""

    id: str
    status: str
    created_at_jalali: str
    last_event: str | None = None
    last_event_at_jalali: str | None = None


# --- errors ---------------------------------------------------------------------


class ConversationNotFound(AppError):
    """Also raised when the backend says 403: the caller must not learn that a
    conversation they may not see exists."""

    status_code = 404
    code = "conversation_not_found"
    title = "Conversation Not Found"


class BackendUnavailable(AppError):
    """The backend is down, slow or broken. In `auto` this means handoff; in `draft`
    it is returned to the caller (AI-1)."""

    status_code = 502
    code = "upstream_unavailable"
    title = "Upstream Unavailable"


class NotImplementedInMvp(AppError):
    status_code = 501
    code = "not_implemented"
    title = "Not Implemented"


# --- the interface --------------------------------------------------------------


@runtime_checkable
class MainBackend(Protocol):
    """§7.3. Every call carries the verified identity; the backend applies its own
    access rules to that user (§6.3, "on behalf of")."""

    async def get_conversation(self, conv_id: str, actor: Actor) -> Conversation: ...

    async def get_messages(self, conv_id: str, actor: Actor, limit: int) -> list[Message]: ...

    async def list_kb_items(self, updated_since: datetime | None) -> list[KbItem]: ...

    async def get_recent_orders(self, actor: Actor, limit: int = 3) -> list[OrderSummary]: ...

    async def post_assistant_message(
        self, conv_id: str, text: str, idem_key: str, meta: dict[str, Any]
    ) -> str: ...

    async def handoff(self, conv_id: str, reason: str) -> None: ...

    async def aclose(self) -> None: ...


@dataclass
class BackendCalls:
    """Call counter used by tests and the shadow runner to assert, for instance, that
    `post_assistant_message` was never called in shadow mode (T6.3)."""

    counts: dict[str, int] = field(default_factory=dict)

    def record(self, name: str) -> None:
        self.counts[name] = self.counts.get(name, 0) + 1

    def __getitem__(self, name: str) -> int:
        return self.counts.get(name, 0)
