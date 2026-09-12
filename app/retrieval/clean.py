"""HTML -> plain text, keeping heading and list structure as markdown (§9.2 step 3).

No extra dependency: the KB bodies are small, well-formed fragments produced by the
backend's editor, so the standard library's HTMLParser is enough and cannot pull in a
parser with its own security surface.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

# Elements whose content is never text.
_DROP = {"script", "style", "noscript", "head", "iframe", "svg", "template"}
# Page furniture that must not end up in the knowledge base (§9.2).
_FURNITURE = {"nav", "footer", "header", "aside", "menu", "form"}
_BLOCK = {
    "p",
    "div",
    "section",
    "article",
    "br",
    "hr",
    "tr",
    "table",
    "blockquote",
    "pre",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "dl",
    "dt",
    "dd",
}
_HEADINGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}

_MULTI_NEWLINE = re.compile(r"\n{3,}")
_TRAILING_SPACE = re.compile(r"[ \t]+\n")
_HTML_TAG_HINT = re.compile(r"<[a-zA-Z/!][^>]*>")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._list_stack: list[str] = []
        self._item_index: list[int] = []

    # --- helpers ---------------------------------------------------------------

    def _emit(self, text: str) -> None:
        self.parts.append(text)

    def _newline(self, count: int = 1) -> None:
        self.parts.append("\n" * count)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _DROP or tag in _FURNITURE:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in _HEADINGS:
            self._newline(2)
            self._emit(_HEADINGS[tag] + " ")
        elif tag in ("ul", "ol"):
            # A nested list continues the same block: each <li> already emits its own
            # newline, so only a top-level list opens a paragraph break.
            if not self._list_stack:
                self._newline(2)
            self._list_stack.append(tag)
            self._item_index.append(0)
        elif tag == "li":
            self._newline()
            depth = max(len(self._list_stack) - 1, 0)
            indent = "  " * depth
            if self._list_stack and self._list_stack[-1] == "ol":
                self._item_index[-1] += 1
                self._emit(f"{indent}{self._item_index[-1]}. ")
            else:
                self._emit(f"{indent}- ")
        elif tag == "br":
            self._newline()
        elif tag in _BLOCK:
            self._newline(2)

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROP or tag in _FURNITURE:
            self._skip_depth = max(self._skip_depth - 1, 0)
            return
        if self._skip_depth:
            return
        if tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
                self._item_index.pop()
            if not self._list_stack:
                self._newline(2)
        elif tag == "li":
            # The next <li> opens with its own newline; emitting one here too would put a
            # blank line between every list item.
            return
        elif tag in _HEADINGS or tag in _BLOCK:
            self._newline(2)

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = re.sub(r"[ \t\r\n]+", " ", data)
        if text.strip():
            self._emit(text if self.parts else text.lstrip())
        elif text and self.parts and not self.parts[-1].endswith((" ", "\n")):
            self._emit(" ")


def looks_like_html(text: str) -> bool:
    return bool(_HTML_TAG_HINT.search(text))


def html_to_text(html: str) -> str:
    """Convert an HTML fragment to text with markdown headings and lists."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return _tidy("".join(parser.parts))


_LIST_ITEM = re.compile(r"^\s+(?:[-*]|\d+\.)\s")


def _tidy(text: str) -> str:
    text = _TRAILING_SPACE.sub("\n", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    # Indentation is meaningful for nested list items and is the only leading space kept.
    lines = [line.rstrip() if _LIST_ITEM.match(line) else line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def clean(body: str) -> str:
    """Clean a KB body, whether it arrives as HTML or as markdown/plain text."""
    if not body:
        return ""
    if looks_like_html(body):
        return html_to_text(body)
    return _tidy(body.replace("\r\n", "\n"))
