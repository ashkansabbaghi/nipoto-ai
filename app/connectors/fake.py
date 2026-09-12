"""In-memory backend backed by JSON fixtures.

Phases 1–4 are built and tested against this, without waiting for the backend API. The
evaluation harness (§12) and the offline shadow run (T6.4) use it too.

It deliberately enforces the same ownership rule as the real backend, so a test that
passes here fails there too if the rule is broken.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from typing import Any

from app.connectors.base import (
    AuthorKind,
    BackendCalls,
    Conversation,
    ConversationNotFound,
    HandledBy,
    KbItem,
    Message,
    NotImplementedInMvp,
    OrderSummary,
)
from app.connectors.mapping import conversation_from_json, message_from_json
from app.core.actor import Actor

DEFAULT_DIR = Path("data/fixtures/conversations")


class FakeMainBackend:
    """Reads conversations from JSON; messages are appended in memory."""

    def __init__(
        self,
        directory: Path | str = DEFAULT_DIR,
        *,
        kb_items: list[KbItem] | None = None,
        orders: dict[str, list[OrderSummary]] | None = None,
    ) -> None:
        self.directory = Path(directory)
        self.calls = BackendCalls()
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, list[Message]] = {}
        self._kb_items = kb_items or []
        self._orders = orders or {}
        self._ids = count(1)
        self._idempotency: dict[str, str] = {}
        self.handoffs: list[tuple[str, str]] = []
        self._load()

    # --- loading ---------------------------------------------------------------

    def _load(self) -> None:
        if not self.directory.is_dir():
            return
        for path in sorted(self.directory.glob("*.json")):
            self.load_file(path)

    def load_file(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data if isinstance(data, list) else [data]:
            conv = conversation_from_json(entry["conversation"])
            self._conversations[conv.id] = conv
            self._messages[conv.id] = [
                message_from_json(m, conv.id) for m in entry.get("messages", [])
            ]

    def add_conversation(self, conv: Conversation, messages: list[Message] | None = None) -> None:
        self._conversations[conv.id] = conv
        self._messages[conv.id] = list(messages or [])

    def set_handled_by(self, conv_id: str, handled_by: HandledBy) -> None:
        conv = self._conversations[conv_id]
        self._conversations[conv_id] = Conversation(
            id=conv.id,
            owner_id=conv.owner_id,
            status=conv.status,
            handled_by=handled_by,
            department_id=conv.department_id,
            staff_id=conv.staff_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )

    def conversation_ids(self) -> list[str]:
        return list(self._conversations)

    # --- the ownership rule ----------------------------------------------------

    def _visible(self, conv_id: str, actor: Actor) -> Conversation:
        """Staff-side actors see every conversation; a user or guest only their own.

        A conversation the actor may not see is reported as *not found*, never as
        forbidden: existence itself must not leak.
        """
        conv = self._conversations.get(conv_id)
        if conv is None:
            raise ConversationNotFound(f"No conversation {conv_id!r}.")
        if not actor.is_staff_side and conv.owner_id != actor.user_id:
            raise ConversationNotFound(f"No conversation {conv_id!r}.")
        return conv

    # --- MainBackend -----------------------------------------------------------

    async def get_conversation(self, conv_id: str, actor: Actor) -> Conversation:
        self.calls.record("get_conversation")
        return self._visible(conv_id, actor)

    async def get_messages(self, conv_id: str, actor: Actor, limit: int) -> list[Message]:
        self.calls.record("get_messages")
        self._visible(conv_id, actor)
        messages = self._messages.get(conv_id, [])
        return messages[-limit:] if limit > 0 else []

    async def list_kb_items(self, updated_since: datetime | None) -> list[KbItem]:
        self.calls.record("list_kb_items")
        if updated_since is None:
            return list(self._kb_items)
        return [
            item
            for item in self._kb_items
            if item.updated_at is not None and item.updated_at > updated_since
        ]

    async def get_recent_orders(self, actor: Actor, limit: int = 3) -> list[OrderSummary]:
        """Phase 6 (B-AI-8). The user comes from `actor`, never from a parameter."""
        self.calls.record("get_recent_orders")
        return self._orders.get(actor.user_id, [])[:limit]

    async def post_assistant_message(
        self, conv_id: str, text: str, idem_key: str, meta: dict[str, Any]
    ) -> str:
        self.calls.record("post_assistant_message")
        if conv_id not in self._conversations:
            raise ConversationNotFound(f"No conversation {conv_id!r}.")
        if idem_key in self._idempotency:
            return self._idempotency[idem_key]
        message = Message(
            id=f"m_fake_{next(self._ids)}",
            author_kind=AuthorKind.ASSISTANT,
            text=text,
            sent_at=datetime.now(UTC),
            conversation_id=conv_id,
        )
        self._messages.setdefault(conv_id, []).append(message)
        self._idempotency[idem_key] = message.id
        return message.id

    async def handoff(self, conv_id: str, reason: str) -> None:
        self.calls.record("handoff")
        if conv_id not in self._conversations:
            raise ConversationNotFound(f"No conversation {conv_id!r}.")
        self.set_handled_by(conv_id, HandledBy.STAFF)
        self.handoffs.append((conv_id, reason))

    async def aclose(self) -> None:
        return None


class BrokenMainBackend:
    """Every call fails. Used to test the AI-1 rule: `draft` errors, `auto` hands off,
    and the service itself stays up."""

    def __init__(self, error: Exception | None = None) -> None:
        from app.connectors.base import BackendUnavailable

        self.error = error or BackendUnavailable("Backend is down.")
        self.calls = BackendCalls()

    async def _fail(self, name: str):
        self.calls.record(name)
        raise self.error

    async def get_conversation(self, conv_id: str, actor: Actor) -> Conversation:
        await self._fail("get_conversation")
        raise AssertionError("unreachable")

    async def get_messages(self, conv_id: str, actor: Actor, limit: int) -> list[Message]:
        await self._fail("get_messages")
        raise AssertionError("unreachable")

    async def list_kb_items(self, updated_since: datetime | None) -> list[KbItem]:
        await self._fail("list_kb_items")
        raise AssertionError("unreachable")

    async def get_recent_orders(self, actor: Actor, limit: int = 3) -> list[OrderSummary]:
        await self._fail("get_recent_orders")
        raise AssertionError("unreachable")

    async def post_assistant_message(
        self, conv_id: str, text: str, idem_key: str, meta: dict[str, Any]
    ) -> str:
        await self._fail("post_assistant_message")
        raise AssertionError("unreachable")

    async def handoff(self, conv_id: str, reason: str) -> None:
        await self._fail("handoff")

    async def aclose(self) -> None:
        return None


__all__ = ["BrokenMainBackend", "FakeMainBackend", "NotImplementedInMvp"]
