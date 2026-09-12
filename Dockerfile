# syntax=docker/dockerfile:1
# Build: uv installs into a virtualenv layer that is cached on uv.lock.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 nipoto

WORKDIR /app
COPY --from=builder --chown=nipoto:nipoto /app/.venv /app/.venv
COPY --chown=nipoto:nipoto app ./app
COPY --chown=nipoto:nipoto migrations ./migrations
COPY --chown=nipoto:nipoto config ./config
COPY --chown=nipoto:nipoto alembic.ini ./

USER nipoto
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8080/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
