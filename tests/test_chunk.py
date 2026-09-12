"""T2.2: chunking (§9.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.retrieval.chunk import (
    BREADCRUMB,
    DOC_MAX_TOKENS,
    FAQ_MAX_TOKENS,
    chunk_doc,
    chunk_document,
    chunk_faq,
    count_tokens,
    split_sections,
)

ROOT = Path(__file__).resolve().parent.parent
KB = json.loads((ROOT / "data" / "kb" / "nipoto_kb.json").read_text(encoding="utf-8"))


def faq_item(**over):
    item = {
        "id": "faq_1",
        "type": "faq",
        "visibility": "public",
        "title": "چطور سفارشم را پیگیری کنم؟",
        "body": "<p>از پنل کاربری بخش سفارش‌ها را باز کنید.</p>",
        "url": "https://help.nipoto.com/faq/1",
        "updated_at": "2026-09-01T10:00:00Z",
    }
    return {**item, **over}


# --- FAQ ---------------------------------------------------------------------------


def test_a_short_faq_is_one_chunk() -> None:
    chunks = chunk_faq("عنوان", "<p>پاسخ کوتاه</p>")
    assert len(chunks) == 1
    assert chunks[0].text.startswith("پرسش: عنوان")
    assert "پاسخ: پاسخ کوتاه" in chunks[0].text


def test_a_short_faq_is_never_split(tmp_path: Path) -> None:
    """The acceptance criterion: a short FAQ stays whole no matter how many paragraphs."""
    body = "\n\n".join(f"<p>پاراگراف {i}</p>" for i in range(6))
    assert len(chunk_faq("عنوان", body)) == 1


def test_a_long_faq_is_split_and_repeats_the_question() -> None:
    long_paragraph = "متن طولانی برای این پاسخ است. " * 40
    body = "\n\n".join(f"<p>{long_paragraph}</p>" for _ in range(4))
    chunks = chunk_faq("سوال بلند", body)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.text.startswith("پرسش: سوال بلند"), "the question repeats in every piece"
        assert chunk.token_count <= FAQ_MAX_TOKENS * 1.2


def test_faq_chunk_carries_the_title_in_its_first_line() -> None:
    chunk = chunk_document(faq_item())[0]
    assert faq_item()["title"] in chunk.text.split("\n")[0]


# --- documents ---------------------------------------------------------------------


def test_sections_split_on_h2_and_h3() -> None:
    text = "# عنوان سند\n\nمقدمه\n\n## بخش یک\n\nمتن یک\n\n### زیربخش\n\nمتن دو"
    sections = split_sections(text)
    assert [s.heading for s in sections] == [None, "بخش یک", "زیربخش"]
    assert sections[0].body.strip() == "مقدمه"


def test_h4_does_not_start_a_new_section() -> None:
    text = "## بخش\n\nمتن\n\n#### ریز\n\nادامه"
    sections = split_sections(text)
    assert [s.heading for s in sections] == ["بخش"]
    assert "#### ریز" in sections[0].body


def test_every_doc_chunk_starts_with_title_and_section() -> None:
    item = {
        "id": "doc_1",
        "type": "doc",
        "visibility": "public",
        "title": "راهنمای برداشت",
        "body": "<h2>پیش از برداشت</h2><p>متن</p><h2>مراحل</h2><p>متن دو</p>",
    }
    chunks = chunk_document(item)
    assert len(chunks) == 2
    assert chunks[0].text.startswith(f"راهنمای برداشت{BREADCRUMB}پیش از برداشت")
    assert chunks[1].text.startswith(f"راهنمای برداشت{BREADCRUMB}مراحل")


def test_a_long_section_is_split_with_overlap() -> None:
    paragraph = "این یک پاراگراف نسبتاً بلند برای آزمون شکستن بخش است. " * 8
    body = "<h2>بخش بلند</h2>" + "".join(f"<p>{paragraph}</p>" for _ in range(6))
    chunks = chunk_doc("عنوان", body)
    assert len(chunks) > 1
    assert all(c.section == "بخش بلند" for c in chunks)
    # The overlap means the tail of one piece reappears at the head of the next.
    assert chunks[0].text.split("\n\n")[-1] in chunks[1].text


def test_an_oversized_single_paragraph_is_kept_whole() -> None:
    """Cutting mid-sentence retrieves worse than one slightly oversized chunk."""
    paragraph = "جمله‌ای بسیار طولانی بدون هیچ پاراگراف دیگری. " * 60
    chunks = chunk_doc("عنوان", f"<h2>بخش</h2><p>{paragraph}</p>")
    assert len(chunks) == 1
    assert chunks[0].token_count > DOC_MAX_TOKENS


def test_a_doc_without_headings_still_produces_a_chunk() -> None:
    chunks = chunk_document(
        {"id": "d", "type": "doc", "visibility": "public", "title": "ت", "body": "<p>متن</p>"}
    )
    assert len(chunks) == 1
    assert chunks[0].section is None


def test_empty_body_produces_no_chunks() -> None:
    item = {"id": "d", "type": "doc", "visibility": "public", "title": "ت", "body": ""}
    assert chunk_document(item) == []


# --- metadata ----------------------------------------------------------------------


def test_metadata_is_complete() -> None:
    chunk = chunk_document(faq_item())[0]
    assert chunk.metadata == {
        "document_id": "faq_1",
        "visibility": "public",
        "type": "faq",
        "title": "چطور سفارشم را پیگیری کنم؟",
        "section": None,
        "url": "https://help.nipoto.com/faq/1",
        "position": 0,
        "updated_at": "2026-09-01T10:00:00Z",
    }


def test_positions_are_contiguous() -> None:
    long_paragraph = "متن طولانی برای این پاسخ است. " * 40
    body = "".join(f"<p>{long_paragraph}</p>" for _ in range(4))
    chunks = chunk_document(faq_item(body=body))
    assert [c.position for c in chunks] == list(range(len(chunks)))
    assert [c.metadata["position"] for c in chunks] == list(range(len(chunks)))


# --- token counting ----------------------------------------------------------------


@pytest.mark.parametrize(("text", "at_least"), [("", 0), ("سلام", 1), ("سلام دنیا " * 100, 200)])
def test_token_count_is_roughly_right(text: str, at_least: int) -> None:
    assert count_tokens(text) >= at_least


def test_token_count_is_adjustable() -> None:
    """§9.12: the budgets are starting points, tuned on the golden set in T2.7."""
    assert FAQ_MAX_TOKENS == 800
    assert DOC_MAX_TOKENS == 500


# --- the real knowledge base -------------------------------------------------------


@pytest.mark.parametrize("item", KB, ids=[item["id"] for item in KB])
def test_every_real_item_chunks_with_a_title_prefix(item: dict) -> None:
    chunks = chunk_document(item)
    assert chunks, item["id"]
    for chunk in chunks:
        first_line = chunk.text.split("\n", 1)[0]
        assert item["title"] in first_line, f"{item['id']} chunk {chunk.position} lost its title"
        assert chunk.metadata["visibility"] == item["visibility"]
        assert chunk.text.strip()
