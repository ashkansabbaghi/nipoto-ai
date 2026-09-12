"""The real connector, over the main backend's REST API (§7.2, contracts/).

Failure behaviour (§7.3): short timeout, retry on GET only, and never a retry on a write.
An unreachable backend surfaces as `BackendUnavailable`, which `auto` turns into a handoff
and `draft` returns as an error (AI-1).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from app.connectors.base import (
    BackendUnavailable,
    Conversation,
    ConversationNotFound,
    KbItem,
    Message,
    OrderSummary,
)
from app.connectors.mapping import (
    conversation_from_json,
    kb_item_from_json,
    message_from_json,
    order_from_json,
)
from app.core.actor import Actor
from app.core.logging import get_logger, get_request_id

log = get_logger("connector")

DEFAULT_TIMEOUT = 2.0
GET_RETRIES = 2  # the initial attempt plus one retry
RETRY_BACKOFF_S = 0.15


class HttpMainBackend:
    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("MAIN_BACKEND_URL is required when MAIN_BACKEND=http")
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout),
            headers=headers,
        )

    # --- plumbing --------------------------------------------------------------

    @staticmethod
    def _on_behalf_of(actor: Actor) -> dict[str, str]:
        """§6.3: the service never asserts an identity that did not come from a verified
        token."""
        headers = {"X-On-Behalf-Of-Sub": actor.user_id, "X-On-Behalf-Of-Role": actor.role}
        request_id = get_request_id()
        if request_id:
            headers["X-Request-Id"] = request_id
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        conv_id: str | None = None,
    ) -> httpx.Response:
        attempts = GET_RETRIES if method == "GET" else 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await self._client.request(
                    method, path, headers=headers, params=params, json=json
                )
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(RETRY_BACKOFF_S)
                    continue
                log.warning("backend_transport_error", method=method, path=path, error=str(exc))
                raise BackendUnavailable("Main backend is unreachable.") from exc

            if response.status_code in (404, 403):
                # 403 is mapped to not-found on purpose: the caller must not learn that a
                # conversation they may not see exists.
                raise ConversationNotFound(f"No conversation {conv_id!r}.")
            if response.status_code >= 500 and attempt + 1 < attempts:
                await asyncio.sleep(RETRY_BACKOFF_S)
                continue
            if response.status_code >= 400:
                log.warning("backend_error", method=method, path=path, status=response.status_code)
                raise BackendUnavailable(
                    f"Main backend returned {response.status_code}.",
                    extra={"upstream_status": response.status_code},
                )
            return response

        raise BackendUnavailable("Main backend is unreachable.") from last_exc

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise BackendUnavailable("Main backend returned a malformed body.") from exc

    # --- MainBackend -----------------------------------------------------------

    async def get_conversation(self, conv_id: str, actor: Actor) -> Conversation:
        """B-AI-2."""
        response = await self._request(
            "GET",
            f"/conversations/{conv_id}",
            headers=self._on_behalf_of(actor),
            conv_id=conv_id,
        )
        return conversation_from_json(self._json(response))

    async def get_messages(self, conv_id: str, actor: Actor, limit: int) -> list[Message]:
        """B-AI-3."""
        response = await self._request(
            "GET",
            f"/conversations/{conv_id}/messages",
            headers=self._on_behalf_of(actor),
            params={"limit": limit},
            conv_id=conv_id,
        )
        body = self._json(response)
        items = body.get("items", body) if isinstance(body, dict) else body
        return [message_from_json(item, conv_id) for item in items]

    async def list_kb_items(self, updated_since: datetime | None) -> list[KbItem]:
        """B-AI-4 (post-MVP; until then the KB is imported manually, §9.2)."""
        params = {"updatedSince": updated_since.isoformat()} if updated_since else None
        response = await self._request("GET", "/kb/items", params=params)
        body = self._json(response)
        items = body.get("items", body) if isinstance(body, dict) else body
        return [kb_item_from_json(item) for item in items]

    async def get_recent_orders(self, actor: Actor, limit: int = 3) -> list[OrderSummary]:
        """B-AI-8 (phase 6). There is no user id parameter: the user comes from `actor`."""
        response = await self._request(
            "GET",
            "/me/orders",
            headers=self._on_behalf_of(actor),
            params={"limit": limit},
        )
        body = self._json(response)
        items = body.get("items", body) if isinstance(body, dict) else body
        return [order_from_json(item) for item in items]

    async def post_assistant_message(
        self, conv_id: str, text: str, idem_key: str, meta: dict[str, Any]
    ) -> str:
        """B-AI-5 (phase 5). A write is never retried; idempotency is the backend's job."""
        response = await self._request(
            "POST",
            f"/conversations/{conv_id}/messages",
            headers={"Idempotency-Key": idem_key},
            json={"text": text, "authorKind": "assistant", "meta": meta},
            conv_id=conv_id,
        )
        return self._json(response)["id"]

    async def handoff(self, conv_id: str, reason: str) -> None:
        """B-AI-6 (phase 5)."""
        await self._request(
            "POST",
            f"/conversations/{conv_id}/handoff",
            json={"reason": reason},
            conv_id=conv_id,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
