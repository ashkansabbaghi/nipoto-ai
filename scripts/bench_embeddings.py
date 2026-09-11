"""Measure the embeddings sidecar (T0.5): dimension, norm and single-query latency.

Usage:
    uv run python scripts/bench_embeddings.py                       # EMBEDDINGS_BASE_URL or :8081
    uv run python scripts/bench_embeddings.py --url http://host:8081/v1 --runs 50
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
import time

import httpx

QUERIES = [
    "برداشت تومان من کی به حسابم می‌نشیند؟",
    "چطور ورود دومرحله‌ای را فعال کنم؟",
    "رمزارز را با شبکه‌ی اشتباه واریز کردم",
    "کارمزد معامله چقدر است",
    "مدارک احراز هویتم رد شد چرا",
    "سقف برداشت روزانه",
    "how do I create an API key",
    "گوشیم گم شده کد دو مرحله ای ندارم",
]


def embed(client: httpx.Client, url: str, model: str, texts: list[str]) -> list[list[float]]:
    resp = client.post(f"{url}/embeddings", json={"model": model, "input": texts})
    resp.raise_for_status()
    return [d["embedding"] for d in sorted(resp.json()["data"], key=lambda d: d["index"])]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--url", default=os.environ.get("EMBEDDINGS_BASE_URL", "http://localhost:8081/v1")
    )
    parser.add_argument("--model", default=os.environ.get("EMBEDDINGS_MODEL", "BAAI/bge-m3"))
    parser.add_argument("--runs", type=int, default=40)
    args = parser.parse_args(argv)

    with httpx.Client(timeout=30) as client:
        vectors = embed(client, args.url, args.model, QUERIES[:1])  # warm-up + shape check
        dim, norm = len(vectors[0]), math.sqrt(sum(x * x for x in vectors[0]))

        latencies = []
        for i in range(args.runs):
            start = time.perf_counter()
            embed(client, args.url, args.model, [QUERIES[i % len(QUERIES)]])
            latencies.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        embed(client, args.url, args.model, QUERIES * 4)
        batch_ms = (time.perf_counter() - start) * 1000

    latencies.sort()
    p95 = latencies[max(0, math.ceil(len(latencies) * 0.95) - 1)]
    print(f"url={args.url} model={args.model}")
    print(f"dim={dim} norm={norm:.4f}")
    print(f"single query: p50={statistics.median(latencies):.0f}ms p95={p95:.0f}ms n={args.runs}")
    print(f"batch of {len(QUERIES) * 4}: {batch_ms:.0f}ms")
    ok = dim == 1024 and statistics.median(latencies) < 200
    print("PASS" if ok else "FAIL (need dim=1024 and p50<200ms)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
