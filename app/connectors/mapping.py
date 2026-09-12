"""Backend wire format (camelCase JSON) -> our domain models.

Shared by the HTTP connector and the JSON fixtures, so both agree on the shape described
in contracts/main-backend.openapi.yaml.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.connectors.base import (
    AuthorKind,
    Conversation,
    ConversationStatus,
    HandledBy,
    KbItem,
    Message,
    OrderSummary,
)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def conversation_from_json(data: dict[str, Any]) -> Conversation:
    return Conversation(
        id=data["id"],
        owner_id=data["userId"],
        status=ConversationStatus(data.get("status", "opened")),
        handled_by=HandledBy(data.get("handledBy", "assistant")),
        department_id=data.get("departmentId"),
        staff_id=data.get("staffId"),
        title=data.get("title"),
        created_at=parse_dt(data.get("createdAt")),
        updated_at=parse_dt(data.get("updatedAt")),
    )


def message_from_json(data: dict[str, Any], conv_id: str | None = None) -> Message:
    return Message(
        id=data["id"],
        author_kind=AuthorKind(data["authorKind"]),
        text=data["text"],
        sent_at=parse_dt(data.get("sentAt")),
        author_id=data.get("authorId"),
        conversation_id=data.get("conversationId", conv_id),
        has_attachment=bool(data.get("hasAttachment", False)),
    )


def kb_item_from_json(data: dict[str, Any]) -> KbItem:
    return KbItem(
        id=data["id"],
        type=data["type"],
        visibility=data["visibility"],
        title=data.get("title", ""),
        body=data.get("body", ""),
        url=data.get("url"),
        updated_at=parse_dt(data.get("updatedAt")),
        deleted=bool(data.get("deleted", False)),
    )


def order_from_json(data: dict[str, Any]) -> OrderSummary:
    return OrderSummary(
        id=data["id"],
        status=data["status"],
        created_at_jalali=data["createdAtJalali"],
        last_event=data.get("lastEvent"),
        last_event_at_jalali=data.get("lastEventAtJalali"),
    )
