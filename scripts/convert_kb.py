"""Convert a main-backend FAQ dump into the KB import format (§9.2) and validate it.

Input: a JSON array of backend FAQ records as returned by `Support.FAQ` (see
new-support `FaqItem`): `{_id|id, question, excerpt?, answer, department|departmentId?,
tags?, updatedAt?, visibility?}`. Records that already look like import items
(`title` + `body` + `type`) are passed through unchanged.

Usage:
    uv run python scripts/convert_kb.py data/kb/raw/faqs.json -o data/kb/nipoto_kb.json
    uv run python scripts/convert_kb.py data/kb/nipoto_kb.json --check
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REQUIRED = ("id", "type", "visibility", "title", "body", "updated_at")
TYPES = {"faq", "doc"}
VISIBILITIES = {"public", "internal"}
FAQ_URL = "https://nipoto.com/faq/{department}/{id}"


def _pick(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def convert_record(record: dict[str, Any], id_prefix: str = "faq_") -> dict[str, Any]:
    if {"title", "body", "type"} <= record.keys():
        return record
    raw_id = str(_pick(record, "id", "_id") or "")
    item_id = raw_id if raw_id.startswith(id_prefix) else f"{id_prefix}{raw_id}"
    department = _pick(record, "department", "departmentId") or ""
    updated = _pick(record, "updatedAt", "updated_at", "createdAt") or datetime.now(UTC).isoformat()
    return {
        "id": item_id,
        "type": "faq",
        "visibility": record.get("visibility") or "public",
        "title": str(_pick(record, "question", "title") or "").strip(),
        "body": str(_pick(record, "answer", "body") or "").strip(),
        "url": FAQ_URL.format(department=department, id=item_id) if department else "",
        "updated_at": updated,
        "_topic": department,
    }


def validate(items: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for i, item in enumerate(items):
        ref = item.get("id") or f"#{i}"
        for key in REQUIRED:
            if not item.get(key):
                errors.append(f"{ref}: missing {key}")
        if item.get("type") not in TYPES:
            errors.append(f"{ref}: type must be one of {sorted(TYPES)}")
        if item.get("visibility") not in VISIBILITIES:
            errors.append(f"{ref}: visibility must be one of {sorted(VISIBILITIES)}")
        if ref in seen:
            errors.append(f"{ref}: duplicate id")
        seen.add(ref)
    return errors


def stats(items: list[dict[str, Any]]) -> str:
    by_type = Counter(f"{it.get('type')}/{it.get('visibility')}" for it in items)
    lines = [f"items: {len(items)}"] + [f"  {k}: {v}" for k, v in sorted(by_type.items())]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--check", action="store_true", help="only validate and print stats")
    args = parser.parse_args(argv)

    records = json.loads(args.input.read_text(encoding="utf-8"))
    items = records if args.check else [convert_record(r) for r in records]
    errors = validate(items)
    print(stats(items))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if args.output and not args.check:
        clean = [{k: v for k, v in it.items() if not k.startswith("_")} for it in items]
        args.output.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
