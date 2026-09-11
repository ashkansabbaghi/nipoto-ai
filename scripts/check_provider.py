"""Validate an OpenAI-compatible LLM provider for nipoto-ai (T0.3).

Checks, per model: a Persian streaming completion (TTFT, total time, `include_usage`)
and a JSON-mode completion (`response_format=json_object`, falling back to plain parsing).
Reads LLM_BASE_URL, LLM_API_KEY, CHAT_MODEL, SMALL_MODEL from the environment / .env.

Usage:
    uv run python scripts/check_provider.py                # CHAT_MODEL and SMALL_MODEL
    uv run python scripts/check_provider.py -m model-a -m model-b --runs 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI, BadRequestError

STREAM_PROMPT = [
    {
        "role": "system",
        "content": "تو دستیار پشتیبانی یک صرافی رمزارز هستی. کوتاه و فارسی جواب بده.",
    },
    {"role": "user", "content": "برداشت تومان من کی به حسابم می‌نشیند؟ در دو جمله توضیح بده."},
]
JSON_PROMPT = [
    {
        "role": "system",
        "content": (
            "فقط JSON برگردان، بدون هیچ متن دیگری. قالب: "
            '{"intent": "question|wants_human|other", "search_query": "...", '
            '"language": "fa|en|other"}'
        ),
    },
    {
        "role": "user",
        "content": "<conversation>\nمشتری: می‌خوام با یه آدم حرف بزنم\n</conversation>",
    },
]


@dataclass
class ModelReport:
    model: str
    stream_ok: bool = False
    usage_in_stream: bool = False
    json_mode: str = "untested"  # native | fallback | failed
    ttft_ms: list[float] = field(default_factory=list)
    total_ms: list[float] = field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    sample: str = ""
    errors: list[str] = field(default_factory=list)


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


async def check_stream(client: AsyncOpenAI, report: ModelReport) -> None:
    start = time.perf_counter()
    first: float | None = None
    parts: list[str] = []
    stream = await client.chat.completions.create(
        model=report.model,
        messages=STREAM_PROMPT,
        stream=True,
        max_tokens=150,
        temperature=0.3,
        stream_options={"include_usage": True},
    )
    async for chunk in stream:
        if chunk.usage:
            report.usage_in_stream = True
            report.prompt_tokens = chunk.usage.prompt_tokens
            report.completion_tokens = chunk.usage.completion_tokens
        if chunk.choices and chunk.choices[0].delta.content:
            if first is None:
                first = time.perf_counter()
            parts.append(chunk.choices[0].delta.content)
    end = time.perf_counter()
    if first is not None:
        report.ttft_ms.append((first - start) * 1000)
    report.total_ms.append((end - start) * 1000)
    report.sample = "".join(parts).strip()
    report.stream_ok = bool(report.sample)


async def check_json(client: AsyncOpenAI, report: ModelReport) -> None:
    try:
        resp = await client.chat.completions.create(
            model=report.model,
            messages=JSON_PROMPT,
            max_tokens=120,
            temperature=0,
            response_format={"type": "json_object"},
        )
        mode = "native"
    except BadRequestError as exc:
        report.errors.append(f"json_object rejected: {exc.message}")
        resp = await client.chat.completions.create(
            model=report.model, messages=JSON_PROMPT, max_tokens=120, temperature=0
        )
        mode = "fallback"
    text = (resp.choices[0].message.content or "").strip()
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start : end + 1])
        report.json_mode = mode if data.get("intent") else "failed"
    except ValueError:
        report.json_mode = "failed"
        report.errors.append(f"unparseable JSON: {text[:120]!r}")


async def run(models: list[str], runs: int, http_client: Any = None) -> list[ModelReport]:
    client = AsyncOpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
        timeout=60,
        http_client=http_client,
    )
    reports = []
    for model in models:
        report = ModelReport(model=model)
        for _ in range(runs):
            try:
                await check_stream(client, report)
            except Exception as exc:
                report.errors.append(f"stream: {type(exc).__name__}: {exc}")
                break
        try:
            await check_json(client, report)
        except Exception as exc:
            report.errors.append(f"json: {type(exc).__name__}: {exc}")
        reports.append(report)
    return reports


def p50(values: list[float]) -> str:
    return f"{statistics.median(values):.0f}" if values else "—"


def to_markdown(reports: list[ModelReport], base_url: str) -> str:
    lines = [
        f"Provider: `{base_url}`",
        "",
        "| model | stream | include_usage | JSON mode | TTFT p50 (ms) | total p50 (ms) "
        "| tokens in/out | price in/out ($/1M) |",
        "|---|---|---|---|---|---|---|---|",
    ]

    def mark(ok: bool) -> str:
        return "✅" if ok else "❌"

    for r in reports:
        lines.append(
            f"| `{r.model}` | {mark(r.stream_ok)} | {mark(r.usage_in_stream)} "
            f"| {r.json_mode} | {p50(r.ttft_ms)} | {p50(r.total_ms)} "
            f"| {r.prompt_tokens or '—'}/{r.completion_tokens or '—'} | _fill in_ |"
        )
    for r in reports:
        lines += ["", f"**{r.model}** sample: {r.sample[:300]}"]
        lines += [f"- error: {e}" for e in r.errors]
    return "\n".join(lines)


def main(argv: list[str] | None = None, http_client: Any = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-m", "--model", action="append", dest="models")
    parser.add_argument("--runs", type=int, default=3, help="stream runs per model (for TTFT)")
    args = parser.parse_args(argv)

    missing = [k for k in ("LLM_BASE_URL", "LLM_API_KEY") if not os.environ.get(k)]
    if missing:
        print(f"missing env: {', '.join(missing)} (set them in .env)", file=sys.stderr)
        return 2
    models = args.models or [
        m for m in (os.environ.get("CHAT_MODEL"), os.environ.get("SMALL_MODEL")) if m
    ]
    if not models:
        print("no model: pass -m or set CHAT_MODEL / SMALL_MODEL", file=sys.stderr)
        return 2

    reports = asyncio.run(run(list(dict.fromkeys(models)), args.runs, http_client))
    print(to_markdown(reports, os.environ["LLM_BASE_URL"]))
    ok = all(r.stream_ok and r.json_mode in ("native", "fallback") for r in reports)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
