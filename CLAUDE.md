# nipoto-ai

Standalone AI support service for Nipoto: knowledge search, staff drafts (`draft`) and
customer auto replies (`auto`, shadow-only in the MVP). Python 3.13 + FastAPI.

- Design doc (source of truth): [AI-SERVICE.fa.md](AI-SERVICE.fa.md). Sections are cited as `§n`.
- Execution plan and task list: [MVP-PLAN.fa.md](MVP-PLAN.fa.md). Tasks are cited as `T<m>.<n>`,
  deviations from the design as `D<n>`. Where the plan is silent, the design doc wins.
- Work one task at a time. Do not touch modules outside the task's "files" list.
  A task is done only when every acceptance criterion passes.

## Principles (mandatory, cite in review)

| # | Rule |
|---|---|
| AI-1 | Independence. Never import main-backend code or read its DB. If the backend is down, `auto` hands off and `draft` returns an error; the service itself stays up. |
| AI-2 | The main backend is the source of truth for conversations, messages, users, orders, `handled_by`. We store only: KB index, audit, feedback, settings/prompts, idempotency keys. |
| AI-3 | Identity only from the verified token. `user_id`/role come from `Actor`, never from a request body and never from model output. |
| AI-4 | Model output is never an authorization decision. The model has no tools; it only produces text and may request a handoff. |
| AI-5 | Provider-agnostic. Switching model = config change (`config/routes.yaml`) + passing evals. |
| AI-6 | Streaming from day one (SSE). |
| AI-7 | Measurable. Every response has a `request_id`, an audit row and can receive feedback. |

## Module boundaries

- Only `app/connectors/` talks to the main backend. Nothing else imports `httpx` for it.
- `app/pipeline/` never knows a provider or model name; it asks `app/llm/` for a *route*
  (`draft.generate`, `auto.generate`, `router.classify`).
- `app/retrieval/search.py::search(query, actor)` is the only search entry point. The visibility
  filter is derived from `actor.role` inside it and is **not a parameter**.
- `user_id` comes only from `Actor` (built in `app/core/auth.py` from a verified JWT).
- Persian normalization is two-sided: ingest and query both call
  `app/retrieval/normalize.py::normalize()`. Never normalize only one side.
- Policy (deny topics, link allowlist, contact, limits) lives in `config/policy.yaml` and is
  enforced server-side, not only in prompts.
- Every prompt change is a **new file** with a new version (`prompts/draft.v2.md`); never edit a
  released version in place. The prompt version is written to the audit row.
- Errors are `application/problem+json` with a stable `code` (see `app/core/errors.py`).

## Tests

- Unit tests make **no network calls**. Use `FakeLLM`, `FakeEmbedder`, `FakeMainBackend`.
- HTTP clients are tested with `respx`.
- Tests that need Postgres are marked `@pytest.mark.db` and skip when the DB is unreachable.
- Table-driven tests for normalization, guardrails and post-processing, with Persian digits.

## Commands

```
make install          # uv sync
make lint test        # must be green before a task is done
make fmt              # ruff fix + format
make up / down        # compose: postgres(pgvector) + embeddings sidecar
make migrate          # alembic upgrade head
make run              # uvicorn on :8080
make keys             # dev RSA keys into .keys/
make token ROLE=staff SUB=u1
make kb-import FILE=data/kb/nipoto_kb.json
make eval-retrieval | eval-answers | shadow-run
make check-provider   # needs LLM_* in .env
make contract-lint    # validate contracts/main-backend.openapi.yaml
```

Tooling: `uv` (deps), `ruff` (lint/format, line length 100), `pytest` + `pytest-asyncio`
(auto mode). Local containers run with `docker compose` or `podman-compose` (auto-detected).

## Conventions

- Code, identifiers, comments and commit messages in English; user-facing text and prompts in
  Persian.
- Async everywhere on the request path (SQLAlchemy 2 async, httpx async, openai async).
- Config via `pydantic-settings` (`app/core/config.py`); see `.env.example`.
- Logs via `structlog`; every log line carries `request_id`. Never log tokens, API keys or
  full customer messages at INFO.
