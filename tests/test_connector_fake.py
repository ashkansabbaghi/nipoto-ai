"""T1.5: FakeMainBackend, above all its ownership rule."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.connectors.base import (
    AuthorKind,
    ConversationNotFound,
    HandledBy,
    KbItem,
    MainBackend,
    OrderSummary,
)
from app.connectors.fake import BrokenMainBackend, FakeMainBackend
from app.core.actor import Actor

FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "conversations"

OWNER = Actor(user_id="u_55", role="user")
OTHER_USER = Actor(user_id="u_99", role="user")
GUEST = Actor(user_id="u_55", role="guest")
STAFF = Actor(user_id="s_1", role="staff")


@pytest.fixture
def backend() -> FakeMainBackend:
    return FakeMainBackend(FIXTURES)


def test_it_satisfies_the_protocol(backend: FakeMainBackend) -> None:
    assert isinstance(backend, MainBackend)


def test_fixtures_load(backend: FakeMainBackend) -> None:
    assert "c_1001" in backend.conversation_ids()


async def test_owner_sees_their_conversation(backend: FakeMainBackend) -> None:
    conv = await backend.get_conversation("c_1001", OWNER)
    assert conv.owner_id == "u_55"
    assert conv.handled_by is HandledBy.ASSISTANT
    assert conv.is_handled_by_assistant


async def test_another_user_gets_conversation_not_found(backend: FakeMainBackend) -> None:
    """Not `forbidden`: the existence of someone else's conversation must not leak."""
    with pytest.raises(ConversationNotFound) as exc:
        await backend.get_conversation("c_1001", OTHER_USER)
    assert exc.value.code == "conversation_not_found"
    assert exc.value.status_code == 404


async def test_a_guest_is_bound_by_the_same_rule(backend: FakeMainBackend) -> None:
    assert (await backend.get_conversation("c_1001", GUEST)).id == "c_1001"
    with pytest.raises(ConversationNotFound):
        await backend.get_conversation("c_2002", GUEST)


async def test_staff_sees_every_conversation(backend: FakeMainBackend) -> None:
    assert (await backend.get_conversation("c_1001", STAFF)).id == "c_1001"
    assert (await backend.get_conversation("c_2002", STAFF)).id == "c_2002"


async def test_missing_conversation_is_not_found(backend: FakeMainBackend) -> None:
    with pytest.raises(ConversationNotFound):
        await backend.get_conversation("c_nope", STAFF)


async def test_messages_are_ownership_checked(backend: FakeMainBackend) -> None:
    with pytest.raises(ConversationNotFound):
        await backend.get_messages("c_1001", OTHER_USER, limit=10)


async def test_messages_return_the_last_n(backend: FakeMainBackend) -> None:
    messages = await backend.get_messages("c_1001", OWNER, limit=2)
    assert [m.id for m in messages] == ["m_2", "m_3"]
    assert messages[0].author_kind is AuthorKind.STAFF
    assert messages[1].author_kind is AuthorKind.USER


async def test_appended_messages_are_visible(backend: FakeMainBackend) -> None:
    message_id = await backend.post_assistant_message("c_1001", "پاسخ", "idem-1", {})
    messages = await backend.get_messages("c_1001", OWNER, limit=10)
    assert messages[-1].id == message_id
    assert messages[-1].author_kind is AuthorKind.ASSISTANT
    assert messages[-1].text == "پاسخ"


async def test_posting_is_idempotent(backend: FakeMainBackend) -> None:
    first = await backend.post_assistant_message("c_1001", "الف", "same-key", {})
    second = await backend.post_assistant_message("c_1001", "ب", "same-key", {})
    assert first == second
    texts = [m.text for m in await backend.get_messages("c_1001", OWNER, limit=10)]
    assert texts.count("ب") == 0


async def test_handoff_flips_handled_by(backend: FakeMainBackend) -> None:
    await backend.handoff("c_1001", "deny_topic")
    conv = await backend.get_conversation("c_1001", OWNER)
    assert conv.handled_by is HandledBy.STAFF
    assert backend.handoffs == [("c_1001", "deny_topic")]


async def test_orders_come_from_the_actor_not_a_parameter() -> None:
    backend = FakeMainBackend(
        FIXTURES,
        orders={
            "u_55": [OrderSummary(id="o1", status="sent", created_at_jalali="۱۴۰۵/۰۶/۱۲")],
            "u_99": [OrderSummary(id="o2", status="paid", created_at_jalali="۱۴۰۵/۰۶/۱۳")],
        },
    )
    assert [o.id for o in await backend.get_recent_orders(OWNER)] == ["o1"]
    assert [o.id for o in await backend.get_recent_orders(OTHER_USER)] == ["o2"]


async def test_kb_items_filter_by_updated_since() -> None:
    def item(item_id: str, month: int) -> KbItem:
        return KbItem(
            id=item_id,
            type="faq",
            visibility="public",
            updated_at=datetime(2026, month, 1, tzinfo=UTC),
        )

    old, new = item("a", 1), item("b", 9)
    backend = FakeMainBackend(FIXTURES, kb_items=[old, new])
    assert {i.id for i in await backend.list_kb_items(None)} == {"a", "b"}
    since = datetime(2026, 6, 1, tzinfo=UTC)
    assert [i.id for i in await backend.list_kb_items(since)] == ["b"]


async def test_calls_are_counted(backend: FakeMainBackend) -> None:
    """T6.3 asserts that shadow mode never writes; the counter is how."""
    await backend.get_conversation("c_1001", OWNER)
    await backend.get_conversation("c_1001", OWNER)
    assert backend.calls["get_conversation"] == 2
    assert backend.calls["post_assistant_message"] == 0


async def test_missing_fixture_dir_is_not_an_error(tmp_path: Path) -> None:
    backend = FakeMainBackend(tmp_path / "nope")
    assert backend.conversation_ids() == []


async def test_broken_backend_raises_upstream_unavailable() -> None:
    backend = BrokenMainBackend()
    with pytest.raises(Exception) as exc:
        await backend.get_conversation("c_1001", STAFF)
    assert exc.value.code == "upstream_unavailable"


def test_env_picks_the_implementation() -> None:
    from app.connectors import build_backend
    from app.connectors.http import HttpMainBackend
    from app.core.config import Settings

    fake = build_backend(Settings(env="test", main_backend="fake", _env_file=None))  # type: ignore[call-arg]
    assert isinstance(fake, FakeMainBackend)

    http = build_backend(
        Settings(  # type: ignore[call-arg]
            env="test",
            main_backend="http",
            main_backend_url="https://backend.test/api",
            _env_file=None,
        )
    )
    assert isinstance(http, HttpMainBackend)
