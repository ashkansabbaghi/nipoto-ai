"""Main-backend connectors. Nothing outside this package talks to the main backend."""

from __future__ import annotations

from app.connectors.base import (
    AuthorKind,
    BackendUnavailable,
    Conversation,
    ConversationNotFound,
    ConversationStatus,
    HandledBy,
    KbItem,
    MainBackend,
    Message,
    OrderSummary,
)
from app.core.config import Settings


def build_backend(settings: Settings) -> MainBackend:
    """Pick the implementation from `MAIN_BACKEND` (fake | http)."""
    if settings.main_backend == "http":
        from app.connectors.http import HttpMainBackend

        return HttpMainBackend(
            settings.main_backend_url or "",
            token=settings.main_backend_token,
        )
    from app.connectors.fake import FakeMainBackend

    return FakeMainBackend(settings.fake_backend_dir)


__all__ = [
    "AuthorKind",
    "BackendUnavailable",
    "Conversation",
    "ConversationNotFound",
    "ConversationStatus",
    "HandledBy",
    "KbItem",
    "MainBackend",
    "Message",
    "OrderSummary",
    "build_backend",
]
