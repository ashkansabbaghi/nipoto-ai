"""T2.1: table-driven tests for §9.3, with Persian digits."""

from __future__ import annotations

import pytest

from app.retrieval.normalize import ZWNJ, normalize

# Every row of the §9.3 table, plus the cases that break naive implementations.
PAIRS: list[tuple[str, str, str]] = [
    # (rule, before, after)
    ("arabic-yeh", "يک", "یک"),
    ("arabic-kaf", "كتاب", "کتاب"),
    ("arabic-yeh-in-sentence", "آيا سفارش من ارسال شده؟", "آیا سفارش من ارسال شده؟"),
    ("alef-maksura", "مصطفى", "مصطفی"),
    ("teh-marbuta", "مرحلة", "مرحله"),
    ("hamza-on-alef", "أحمد", "احمد"),
    ("hamza-under-alef", "إيران", "ایران"),
    ("persian-digits", "۱۲۳", "123"),
    ("arabic-indic-digits", "١٢٣", "123"),
    ("digits-in-text", "سفارش شماره ۱۲۳۴۵", "سفارش شماره 12345"),
    ("mixed-digits", "۱۲ و 34 و ٥٦", "12 و 34 و 56"),
    ("arabic-decimal-separator", "۳٫۵", "3.5"),
    ("half-space-spaced-mi", "می شود", f"می{ZWNJ}شود"),
    ("half-space-attached-mi", "میشود", f"می{ZWNJ}شود"),
    ("half-space-spaced-nemi", "نمی رود", f"نمی{ZWNJ}رود"),
    ("half-space-attached-nemi", "نمیرود", f"نمی{ZWNJ}رود"),
    ("half-space-already-correct", f"می{ZWNJ}شود", f"می{ZWNJ}شود"),
    ("suffix-ha", "کتاب ها", f"کتاب{ZWNJ}ها"),
    ("suffix-haye", "کتاب های من", f"کتاب{ZWNJ}های من"),
    ("suffix-tar", "بزرگ تر", f"بزرگ{ZWNJ}تر"),
    ("suffix-tarin", "بزرگ ترین", f"بزرگ{ZWNJ}ترین"),
    ("tatweel", "ســلام", "سلام"),
    ("tatweel-long", "خــــوش آمدید", "خوش آمدید"),
    ("diacritics", "مَن", "من"),
    ("diacritics-tashdid", "مُحَمَّد", "محمد"),
    ("multiple-spaces", "چند   فاصله", "چند فاصله"),
    ("leading-trailing-space", "  سلام  ", "سلام"),
    ("tab", "سلام\tدنیا", "سلام دنیا"),
    ("zero-width-space", "سلام​دنیا", "سلامدنیا"),
    ("zero-width-joiner", "سلام‍دنیا", "سلامدنیا"),
    ("bidi-marks", "‏سلام‎", "سلام"),
    ("bom", "﻿سلام", "سلام"),
    ("soft-hyphen", "سلام­dنیا", "سلامdنیا"),
    ("empty", "", ""),
    ("only-space", "   ", ""),
]


@pytest.mark.parametrize(("rule", "before", "after"), PAIRS, ids=[p[0] for p in PAIRS])
def test_normalize_table(rule: str, before: str, after: str) -> None:
    assert normalize(before) == after


def test_at_least_twenty_pairs() -> None:
    """The acceptance criterion for T2.1."""
    assert len(PAIRS) >= 20


# --- words that must NOT be split ------------------------------------------------


@pytest.mark.parametrize("word", ["میز", "میدان", "میهن", "میلاد", "میوه", "کمیته", "تقسیم"])
def test_ordinary_words_starting_with_mi_are_left_alone(word: str) -> None:
    """A bare "می" prefix rule would corrupt these; only known verb stems are split."""
    assert normalize(word) == word


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("میداند", f"می{ZWNJ}داند"),
        ("نمیدانم", f"نمی{ZWNJ}دانم"),
        ("میگفت", f"می{ZWNJ}گفت"),
        ("میفرستد", f"می{ZWNJ}فرستد"),
    ],
)
def test_known_verb_stems_are_split(before: str, after: str) -> None:
    assert normalize(before) == after


# --- properties -------------------------------------------------------------------


@pytest.mark.parametrize(("rule", "before", "_after"), PAIRS, ids=[p[0] for p in PAIRS])
def test_normalize_is_idempotent(rule: str, before: str, _after: str) -> None:
    once = normalize(before)
    assert normalize(once) == once


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("آيا هزينه ارسال ۲۰ هزار است؟", "آیا هزینه ارسال 20 هزار است؟"),
        ("سفارش من كي ميرسد", f"سفارش من کی می{ZWNJ}رسد"),
        ("كتاب ها را برگرداندم", f"کتاب{ZWNJ}ها را برگرداندم"),
    ],
)
def test_two_sided_normalisation_makes_variants_equal(a: str, b: str) -> None:
    """The point of §9.3: a query written one way must match a document written the
    other. Ingest and search both call this function."""
    assert normalize(a) == normalize(b)


def test_line_breaks_survive() -> None:
    """Chunking splits on paragraphs (§9.4), so newlines must not be collapsed."""
    text = "عنوان\n\nپاراگراف اول\nخط دوم"
    assert normalize(text) == "عنوان\n\nپاراگراف اول\nخط دوم"


def test_three_or_more_blank_lines_collapse_to_one() -> None:
    assert normalize("الف\n\n\n\nب") == "الف\n\nب"


def test_latin_and_punctuation_are_untouched() -> None:
    assert normalize("Nipoto v2 (beta) — 50% off!") == "Nipoto v2 (beta) — 50% off!"


def test_urls_survive() -> None:
    assert normalize("https://help.nipoto.com/faq?id=۴۲") == "https://help.nipoto.com/faq?id=42"


def test_stray_half_space_at_a_word_edge_is_dropped() -> None:
    assert normalize(f"سلام{ZWNJ} دنیا") == "سلام دنیا"
    assert normalize(f"{ZWNJ}سلام") == "سلام"


def test_repeated_half_spaces_collapse() -> None:
    assert normalize(f"می{ZWNJ}{ZWNJ}شود") == f"می{ZWNJ}شود"
