import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import convert_kb  # noqa: E402


def test_kb_file_is_valid():
    items = json.loads((ROOT / "data/kb/nipoto_kb.json").read_text(encoding="utf-8"))
    assert convert_kb.validate(items) == []
    assert len(items) >= 40
    assert {it["visibility"] for it in items} == {"public", "internal"}


def test_convert_backend_faq_record():
    record = {
        "_id": "42",
        "question": " پیگیری سفارش ",
        "excerpt": "…",
        "answer": "<p>از بخش سفارش‌ها</p>",
        "department": "deposit",
        "tags": ["x"],
        "updatedAt": "2026-09-01T10:00:00Z",
    }
    item = convert_kb.convert_record(record)
    assert item["id"] == "faq_42"
    assert item["title"] == "پیگیری سفارش"
    assert item["visibility"] == "public"
    assert item["url"] == "https://nipoto.com/faq/deposit/faq_42"
    assert convert_kb.validate([item]) == []


def test_validate_reports_duplicates_and_missing_visibility():
    items = [
        {"id": "a", "type": "faq", "visibility": "public", "title": "t", "body": "b",
         "updated_at": "2026-01-01"},
        {"id": "a", "type": "faq", "title": "t", "body": "b", "updated_at": "2026-01-01"},
    ]  # fmt: skip
    errors = convert_kb.validate(items)
    assert "a: duplicate id" in errors
    assert any("missing visibility" in e for e in errors)
