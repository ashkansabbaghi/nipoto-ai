"""T1.5: HttpMainBackend against the contract, with respx."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.connectors.base import BackendUnavailable, ConversationNotFound, HandledBy
from app.connectors.http import HttpMainBackend
from app.core.actor import Actor
from app.core.logging import set_request_id

BASE = "https://backend.test/api"
STAFF = Actor(user_id="s_1", role="staff")
USER = Actor(user_id="u_55", role="user")

CONVERSATION = {
    "id": "c_1001",
    "userId": "u_55",
    "status": "opened",
    "handledBy": "assistant",
    "title": "ارسال سفارش",
    "createdAt": "2026-09-10T08:15:00Z",
}
MESSAGES = {
    "items": [
        {"id": "m_1", "authorKind": "user", "text": "سلام", "sentAt": "2026-09-10T08:15:00Z"},
        {"id": "m_2", "authorKind": "staff", "text": "بله؟", "sentAt": "2026-09-10T08:16:00Z"},
    ]
}


@pytest.fixture
def backend() -> HttpMainBackend:
    return HttpMainBackend(BASE, token="service-token", timeout=1.0)


def test_url_is_required() -> None:
    with pytest.raises(ValueError, match="MAIN_BACKEND_URL"):
        HttpMainBackend("")


@respx.mock
async def test_get_conversation_maps_the_contract(backend: HttpMainBackend) -> None:
    route = respx.get(f"{BASE}/conversations/c_1001").mock(
        return_value=httpx.Response(200, json=CONVERSATION)
    )
    conv = await backend.get_conversation("c_1001", USER)
    assert route.called
    assert conv.id == "c_1001"
    assert conv.owner_id == "u_55"  # userId -> owner_id
    assert conv.handled_by is HandledBy.ASSISTANT
    assert conv.created_at is not None


@respx.mock
async def test_every_call_carries_the_verified_identity(backend: HttpMainBackend) -> None:
    """§6.3 "on behalf of": sub and role come from the Actor, never from a body."""
    set_request_id("req_abc")
    route = respx.get(f"{BASE}/conversations/c_1001").mock(
        return_value=httpx.Response(200, json=CONVERSATION)
    )
    await backend.get_conversation("c_1001", USER)
    headers = route.calls.last.request.headers
    assert headers["X-On-Behalf-Of-Sub"] == "u_55"
    assert headers["X-On-Behalf-Of-Role"] == "user"
    assert headers["X-Request-Id"] == "req_abc"
    assert headers["Authorization"] == "Bearer service-token"


@respx.mock
async def test_messages_are_mapped_and_limited(backend: HttpMainBackend) -> None:
    route = respx.get(f"{BASE}/conversations/c_1001/messages").mock(
        return_value=httpx.Response(200, json=MESSAGES)
    )
    messages = await backend.get_messages("c_1001", STAFF, limit=2)
    assert [m.id for m in messages] == ["m_1", "m_2"]
    assert route.calls.last.request.url.params["limit"] == "2"


@respx.mock
async def test_a_bare_list_body_also_works(backend: HttpMainBackend) -> None:
    respx.get(f"{BASE}/conversations/c_1001/messages").mock(
        return_value=httpx.Response(200, json=MESSAGES["items"])
    )
    assert len(await backend.get_messages("c_1001", STAFF, limit=5)) == 2


@respx.mock
@pytest.mark.parametrize("status", [403, 404])
async def test_403_and_404_both_become_conversation_not_found(
    backend: HttpMainBackend, status: int
) -> None:
    """A 403 must not tell the caller the conversation exists."""
    respx.get(f"{BASE}/conversations/c_x").mock(return_value=httpx.Response(status))
    with pytest.raises(ConversationNotFound) as exc:
        await backend.get_conversation("c_x", USER)
    assert exc.value.code == "conversation_not_found"


@respx.mock
async def test_transport_error_becomes_upstream_unavailable(backend: HttpMainBackend) -> None:
    respx.get(f"{BASE}/conversations/c_1001").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(BackendUnavailable) as exc:
        await backend.get_conversation("c_1001", USER)
    assert exc.value.code == "upstream_unavailable"
    assert exc.value.status_code == 502


@respx.mock
async def test_timeout_becomes_upstream_unavailable(backend: HttpMainBackend) -> None:
    respx.get(f"{BASE}/conversations/c_1001").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(BackendUnavailable):
        await backend.get_conversation("c_1001", USER)


@respx.mock
async def test_get_is_retried_once(backend: HttpMainBackend) -> None:
    route = respx.get(f"{BASE}/conversations/c_1001").mock(
        side_effect=[httpx.ConnectError("down"), httpx.Response(200, json=CONVERSATION)]
    )
    conv = await backend.get_conversation("c_1001", USER)
    assert conv.id == "c_1001"
    assert route.call_count == 2


@respx.mock
async def test_a_500_on_get_is_retried(backend: HttpMainBackend) -> None:
    route = respx.get(f"{BASE}/conversations/c_1001").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json=CONVERSATION)]
    )
    assert (await backend.get_conversation("c_1001", USER)).id == "c_1001"
    assert route.call_count == 2


@respx.mock
async def test_a_write_is_never_retried(backend: HttpMainBackend) -> None:
    """Retrying a POST could post the same reply twice."""
    route = respx.post(f"{BASE}/conversations/c_1001/messages").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json={"id": "m_9"})]
    )
    with pytest.raises(BackendUnavailable):
        await backend.post_assistant_message("c_1001", "سلام", "idem-1", {})
    assert route.call_count == 1


@respx.mock
async def test_post_assistant_message_sends_the_idempotency_key(backend: HttpMainBackend) -> None:
    route = respx.post(f"{BASE}/conversations/c_1001/messages").mock(
        return_value=httpx.Response(200, json={"id": "m_9"})
    )
    message_id = await backend.post_assistant_message("c_1001", "سلام", "idem-7", {"a": 1})
    assert message_id == "m_9"
    request = route.calls.last.request
    assert request.headers["Idempotency-Key"] == "idem-7"
    import json

    body = json.loads(request.content)
    assert body["authorKind"] == "assistant"
    assert body["text"] == "سلام"


@respx.mock
async def test_handoff_sends_the_reason(backend: HttpMainBackend) -> None:
    import json

    route = respx.post(f"{BASE}/conversations/c_1001/handoff").mock(
        return_value=httpx.Response(204)
    )
    await backend.handoff("c_1001", "low_confidence")
    assert json.loads(route.calls.last.request.content) == {"reason": "low_confidence"}


@respx.mock
async def test_kb_items_are_mapped(backend: HttpMainBackend) -> None:
    respx.get(f"{BASE}/kb/items").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "faq_1",
                        "type": "faq",
                        "visibility": "public",
                        "title": "عنوان",
                        "body": "متن",
                        "updatedAt": "2026-09-01T00:00:00Z",
                    }
                ]
            },
        )
    )
    items = await backend.list_kb_items(None)
    assert items[0].id == "faq_1"
    assert items[0].updated_at is not None
    assert items[0].deleted is False


@respx.mock
async def test_orders_take_no_user_id_parameter(backend: HttpMainBackend) -> None:
    route = respx.get(f"{BASE}/me/orders").mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"id": "o1", "status": "sent", "createdAtJalali": "۱۴۰۵/۰۶/۱۲"}]},
        )
    )
    orders = await backend.get_recent_orders(USER, limit=3)
    assert orders[0].created_at_jalali == "۱۴۰۵/۰۶/۱۲"
    params = route.calls.last.request.url.params
    assert "userId" not in params
    assert route.calls.last.request.headers["X-On-Behalf-Of-Sub"] == "u_55"


@respx.mock
async def test_malformed_body_is_upstream_unavailable(backend: HttpMainBackend) -> None:
    respx.get(f"{BASE}/conversations/c_1001").mock(
        return_value=httpx.Response(200, content=b"<html>oops</html>")
    )
    with pytest.raises(BackendUnavailable):
        await backend.get_conversation("c_1001", USER)
