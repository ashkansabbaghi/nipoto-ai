"""T2.2: HTML cleaning (§9.2 step 3)."""

from __future__ import annotations

import pytest

from app.retrieval.clean import clean, html_to_text, looks_like_html


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>سلام</p>", "سلام"),
        ("<p>یک</p><p>دو</p>", "یک\n\nدو"),
        ("<h2>عنوان</h2><p>متن</p>", "## عنوان\n\nمتن"),
        ("<h1>الف</h1><h3>ب</h3>", "# الف\n\n### ب"),
        ("<ul><li>یک</li><li>دو</li></ul>", "- یک\n- دو"),
        ("<ol><li>اول</li><li>دوم</li></ol>", "1. اول\n2. دوم"),
        ("<p>خط<br>بعدی</p>", "خط\nبعدی"),
        ("<p>متن <strong>پررنگ</strong> ادامه</p>", "متن پررنگ ادامه"),
        ("<p>لینک <a href='https://x.test'>اینجا</a></p>", "لینک اینجا"),
        ("<p>&laquo;نقل&raquo; &amp; بقیه</p>", "«نقل» & بقیه"),
        ("<p></p>", ""),
    ],
)
def test_html_to_markdownish_text(html: str, expected: str) -> None:
    assert html_to_text(html) == expected


@pytest.mark.parametrize(
    "html",
    [
        "<p>متن</p><script>alert(1)</script>",
        "<p>متن</p><style>p{color:red}</style>",
        "<nav>منو اصلی</nav><p>متن</p>",
        "<p>متن</p><footer>تمام حقوق محفوظ است</footer>",
        "<aside>تبلیغ</aside><p>متن</p>",
    ],
)
def test_furniture_and_scripts_are_dropped(html: str) -> None:
    """Menus, footers and scripts must never reach the knowledge base (§9.2)."""
    assert html_to_text(html) == "متن"


def test_nested_lists_are_indented() -> None:
    html = "<ul><li>الف<ul><li>الف-۱</li></ul></li><li>ب</li></ul>"
    assert html_to_text(html) == "- الف\n  - الف-۱\n- ب"


def test_whitespace_is_collapsed() -> None:
    assert html_to_text("<p>چند    فاصله\n\n  و خط</p>") == "چند فاصله و خط"


def test_plain_text_passes_through() -> None:
    assert clean("یک خط\n\nدو خط") == "یک خط\n\nدو خط"


def test_markdown_input_is_kept() -> None:
    assert clean("## عنوان\n\nمتن") == "## عنوان\n\nمتن"


def test_empty_body() -> None:
    assert clean("") == ""


@pytest.mark.parametrize(
    ("text", "expected"),
    [("<p>x</p>", True), ("متن ساده", False), ("۲ < ۳ و ۵ > ۴", False), ("<h2>x</h2>", True)],
)
def test_looks_like_html(text: str, expected: bool) -> None:
    assert looks_like_html(text) is expected


def test_unclosed_tags_do_not_crash() -> None:
    assert "متن" in html_to_text("<p>متن<div><span>ادامه")


def test_real_kb_bodies_clean_without_tags() -> None:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    items = json.loads((root / "data" / "kb" / "nipoto_kb.json").read_text(encoding="utf-8"))
    for item in items:
        text = clean(item["body"])
        assert "<" not in text or not looks_like_html(text), item["id"]
        assert text.strip(), item["id"]
