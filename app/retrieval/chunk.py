"""Chunking (§9.4).

FAQ entries stay whole; documents are split on their h2/h3 headings. Every chunk starts
with "title › section" so that it still means something on its own — a chunk that only
says "do this from settings" cannot be retrieved.

The token budgets are starting points, tuned on the golden set in T2.7 (§9.12).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.retrieval.clean import clean

FAQ_MAX_TOKENS = 800
DOC_MAX_TOKENS = 500
DOC_OVERLAP_TOKENS = 50

BREADCRUMB = " › "
QUESTION_PREFIX = "پرسش: "
ANSWER_PREFIX = "پاسخ: "

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_PARAGRAPH_SPLIT = re.compile(r"\n{2,}")


def count_tokens(text: str) -> int:
    """Approximate token count.

    Persian is tokenised at roughly 2.5 characters per token by the multilingual models
    we use; whitespace-splitting under-counts badly. Deliberately cheap and replaceable:
    ingest runs offline and the number only steers chunk size.
    """
    if not text:
        return 0
    return max(1, round(len(text) / 2.5))


@dataclass(frozen=True, slots=True)
class Chunk:
    text: str
    position: int
    section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        return count_tokens(self.text)


def _prefix(title: str, section: str | None) -> str:
    if section and section != title:
        return f"{title}{BREADCRUMB}{section}"
    return title


def _split_paragraphs(text: str) -> list[str]:
    return [part.strip() for part in _PARAGRAPH_SPLIT.split(text) if part.strip()]


def _pack(paragraphs: list[str], max_tokens: int, overlap_tokens: int = 0) -> list[str]:
    """Group paragraphs into pieces of at most `max_tokens`, with an optional overlap.

    A single paragraph longer than the budget is kept whole rather than cut mid-sentence:
    a truncated sentence retrieves worse than a slightly oversized chunk.
    """
    pieces: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for paragraph in paragraphs:
        tokens = count_tokens(paragraph)
        if current and current_tokens + tokens > max_tokens:
            pieces.append("\n\n".join(current))
            current, current_tokens = _carry_over(current, overlap_tokens)
        current.append(paragraph)
        current_tokens += tokens

    if current:
        pieces.append("\n\n".join(current))
    return pieces


def _carry_over(current: list[str], overlap_tokens: int) -> tuple[list[str], int]:
    """The tail of the previous piece, repeated at the start of the next one."""
    if overlap_tokens <= 0:
        return [], 0
    carried: list[str] = []
    total = 0
    for paragraph in reversed(current):
        tokens = count_tokens(paragraph)
        if total + tokens > overlap_tokens:
            break
        carried.insert(0, paragraph)
        total += tokens
    return carried, total


# --- FAQ --------------------------------------------------------------------------


def chunk_faq(title: str, body: str, *, max_tokens: int = FAQ_MAX_TOKENS) -> list[Chunk]:
    """One chunk of "پرسش: … / پاسخ: …". Only a very long answer is split, and then the
    question is repeated in every piece."""
    answer = clean(body)
    head = f"{QUESTION_PREFIX}{title}"
    whole = f"{head}\n{ANSWER_PREFIX}{answer}"
    if count_tokens(whole) <= max_tokens:
        return [Chunk(text=whole, position=0, section=None)]

    paragraphs = _split_paragraphs(answer)
    question_tokens = count_tokens(head) + 2
    pieces = _pack(paragraphs, max(max_tokens - question_tokens, 1))
    return [
        Chunk(text=f"{head}\n{ANSWER_PREFIX}{piece}", position=index, section=None)
        for index, piece in enumerate(pieces)
    ]


# --- documents --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Section:
    heading: str | None
    level: int
    body: str


def split_sections(text: str) -> list[_Section]:
    """Split markdown text on h2/h3. h1 is treated as the document title, not a section."""
    sections: list[_Section] = []
    heading: str | None = None
    level = 0
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body or heading:
            sections.append(_Section(heading=heading, level=level, body=body))

    for line in text.split("\n"):
        match = _HEADING.match(line.strip())
        if match and len(match.group(1)) in (1, 2, 3):
            depth = len(match.group(1))
            if depth == 1:
                # h1 repeats the document title; drop it and keep going.
                flush()
                buffer = []
                heading, level = None, 0
                continue
            flush()
            buffer = []
            heading, level = match.group(2).strip(), depth
        else:
            buffer.append(line)
    flush()
    return [section for section in sections if section.body or section.heading]


def chunk_doc(
    title: str,
    body: str,
    *,
    max_tokens: int = DOC_MAX_TOKENS,
    overlap_tokens: int = DOC_OVERLAP_TOKENS,
) -> list[Chunk]:
    text = clean(body)
    chunks: list[Chunk] = []
    position = 0

    for section in split_sections(text):
        if not section.body.strip():
            continue
        pieces = _pack(_split_paragraphs(section.body), max_tokens, overlap_tokens)
        for piece in pieces:
            chunks.append(Chunk(text=piece, position=position, section=section.heading))
            position += 1

    if not chunks and text.strip():
        chunks.append(Chunk(text=text.strip(), position=0, section=None))
    return chunks


# --- entry point ------------------------------------------------------------------


def chunk_document(item: dict[str, Any]) -> list[Chunk]:
    """Chunk one KB item (§9.2 format) and attach the §9.4 metadata.

    Every chunk text is prefixed with "title › section"; the prefix is part of the text
    that gets embedded, not only metadata.

    A document that is too short to be useful is *not* silently dropped here — rejecting
    it belongs to ingest validation, which reports a reason (§9.2 step 2).
    """
    title = (item.get("title") or "").strip()
    body = item.get("body") or ""
    doc_type = item.get("type", "doc")

    raw = chunk_faq(title, body) if doc_type == "faq" else chunk_doc(title, body)

    chunks: list[Chunk] = []
    for chunk in raw:
        prefix = _prefix(title, chunk.section)
        # A FAQ chunk opens with "پرسش: <title>", so the title is already in the first
        # line; prefixing again would only repeat it.
        first_line = chunk.text.split("\n", 1)[0]
        text = chunk.text if title and title in first_line else f"{prefix}\n{chunk.text}"
        if not text.strip():
            continue
        chunks.append(
            Chunk(
                text=text,
                position=len(chunks),
                section=chunk.section,
                metadata={
                    "document_id": item.get("id"),
                    "visibility": item.get("visibility"),
                    "type": doc_type,
                    "title": title,
                    "section": chunk.section,
                    "url": item.get("url"),
                    "position": len(chunks),
                    "updated_at": item.get("updated_at"),
                },
            )
        )
    return chunks
