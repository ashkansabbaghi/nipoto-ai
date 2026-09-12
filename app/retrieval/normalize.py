"""Persian text normalisation (§9.3).

One function, called by **both** ingest and query (T2.1). Normalising only one side
silently loses matches, so `normalize()` is the single entry point for both.

D10: implemented here rather than on top of `hazm`, whose dependency tree is heavy. The
half-space rules are the only part `hazm` does better (it carries a verb lexicon); see
`VERB_STEMS` below for how that is approximated.
"""

from __future__ import annotations

import re
import unicodedata

ZWNJ = "‌"  # half-space

# Invisible characters that change nothing visually but break exact matching.
_INVISIBLE = dict.fromkeys(
    [
        0x200B,  # zero-width space
        0x200D,  # zero-width joiner
        0x200E,  # LRM
        0x200F,  # RLM
        0x202A,  # LRE
        0x202B,  # RLE
        0x202C,  # PDF
        0x202D,  # LRO
        0x202E,  # RLO
        0x2066,  # LRI
        0x2067,  # RLI
        0x2068,  # FSI
        0x2069,  # PDI
        0x00AD,  # soft hyphen
        0xFEFF,  # BOM
        0x0640,  # tatweel (kashida)
    ]
)

# Arabic letters that have a Persian counterpart, plus hamza forms folded onto alef so
# that "أحمد" and "احمد" match.
_LETTERS = str.maketrans(
    {
        "ي": "ی",  # ي -> ی
        "ى": "ی",  # ى -> ی
        "ك": "ک",  # ك -> ک
        "ة": "ه",  # ة -> ه
        "أ": "ا",  # أ -> ا
        "إ": "ا",  # إ -> ا
        "ؤ": "و",  # ؤ -> و
        "ئ": "ی",  # ئ -> ی
        "ۀ": "ه",  # ۀ -> ه
    }
)

# Persian (۰-۹) and Arabic-Indic (٠-٩) digits to ASCII.
_DIGITS = str.maketrans(
    {
        **{chr(0x06F0 + i): str(i) for i in range(10)},
        **{chr(0x0660 + i): str(i) for i in range(10)},
        "٫": ".",  # Arabic decimal separator
        "٬": "",  # Arabic thousands separator
    }
)

# Harakat and other combining marks: َ ُ ِ ّ ً ٌ ٍ ْ ٰ
_DIACRITICS = re.compile(r"[ً-ٰٟۖ-ۭ]")

# Suffixes that take a half-space when written separately: "کتاب ها" -> "کتاب‌ها".
_SUFFIXES = ("ها", "های", "هایی", "هایم", "هایت", "هایش", "تر", "تری", "ترین")

# Verb stems after which an attached "می"/"نمی" is certainly a prefix. Splitting on a bare
# "می" would corrupt ordinary words such as "میز", "میدان" or "میهن", so the split only
# happens for stems on this list. Anything else is left as written.
# fmt: off
VERB_STEMS = (
    "شود", "شوم", "شوی", "شویم", "شوید", "شوند",
    "شد", "شدم", "شدی", "شدیم", "شدید", "شدند",
    "کند", "کنم", "کنی", "کنیم", "کنید", "کنند",
    "کرد", "کردم", "کردی", "کردیم", "کردید", "کردند",
    "رود", "روم", "روی", "رویم", "روید", "روند",
    "رفت", "رفتم", "رفتی", "رفتیم", "رفتید", "رفتند",
    "آید", "آیم", "آیی", "آییم", "آیید", "آیند",
    "آمد", "آمدم", "آمدی", "آمدیم", "آمدید", "آمدند",
    "تواند", "توانم", "توانی", "توانیم", "توانید", "توانند",
    "توانست", "توانستم", "توانستند", "گیرد", "گیرم", "گیری",
    "گیریم", "گیرید", "گیرند", "گرفت", "گرفتم", "گرفتیم",
    "گرفتند", "دهد", "دهم", "دهی", "دهیم", "دهید",
    "دهند", "داد", "دادم", "دادیم", "دادند", "داند",
    "دانم", "دانی", "دانیم", "دانید", "دانند", "دانست",
    "دانستم", "دانستند", "خواهد", "خواهم", "خواهی", "خواهیم",
    "خواهید", "خواهند", "خواست", "خواستم", "خواستند", "بیند",
    "بینم", "بینی", "بینیم", "بینید", "بینند", "دید",
    "دیدم", "دیدیم", "دیدند", "گوید", "گویم", "گویی",
    "گوییم", "گویید", "گویند", "گفت", "گفتم", "گفتیم",
    "گفتند", "ماند", "مانم", "مانیم", "مانند", "ماندم",
    "رسد", "رسم", "رسیم", "رسند", "رسید", "رسیدم",
    "رسیدند", "باشد", "باشم", "باشی", "باشیم", "باشید",
    "باشند", "شناسد", "شناسم", "شناسیم", "شناسند", "شناخت",
    "فرستد", "فرستم", "فرستیم", "فرستند", "فرستاد", "فرستادم",
    "فرستادند", "پذیرد", "پذیرم", "پذیریم", "پذیرند", "پذیرفت",
    "افتد", "افتم", "افتیم", "افتند", "افتاد", "خورد",
    "خورم", "خوریم", "خورند", "برد", "برم", "بریم",
    "برند", "بردم", "بندد", "بندم", "بندیم", "بندند",
    "بست", "نویسد", "نویسم", "نویسیم", "نویسند", "نوشت",
)
# fmt: on

_PREFIX_SPACED = re.compile(r"(?<![؀-ۿ])(ن?می)[ ‌]+(?=[؀-ۿ])")
_PREFIX_ATTACHED = re.compile(
    r"(?<![؀-ۿ])(ن?می)(" + "|".join(sorted(VERB_STEMS, key=len, reverse=True)) + r")"
    r"(?![؀-ۿ])"
)
_SUFFIX_SPACED = re.compile(r"(?<=[؀-ۿ]{2})[ ‌]+(" + "|".join(_SUFFIXES) + r")(?![؀-ۿ])")
_ZWNJ_RUN = re.compile(rf"{ZWNJ}{{2,}}")
_ZWNJ_AT_EDGE = re.compile(rf"(?<![؀-ۿ]){ZWNJ}|{ZWNJ}(?![؀-ۿ])")
_SPACES = re.compile(r"[^\S\n]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalize(text: str) -> str:
    """Return the canonical form of Persian text (§9.3).

    Handles Arabic letter variants, Persian and Arabic-Indic digits, half-spaces for the
    "می"/"نمی" prefix and the "ها"/"تر" suffixes, tatweel, diacritics, invisible
    characters and repeated whitespace. Line breaks are preserved; chunking depends on
    them (§9.4).
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_INVISIBLE)
    text = text.translate(_LETTERS)
    text = text.translate(_DIGITS)
    text = _DIACRITICS.sub("", text)

    text = _PREFIX_SPACED.sub(r"\1" + ZWNJ, text)
    text = _PREFIX_ATTACHED.sub(r"\1" + ZWNJ + r"\2", text)
    text = _SUFFIX_SPACED.sub(ZWNJ + r"\1", text)

    text = _ZWNJ_RUN.sub(ZWNJ, text)
    text = _ZWNJ_AT_EDGE.sub("", text)

    text = text.replace("\t", " ")
    text = _SPACES.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()
