UV      ?= uv
RUN     := $(UV) run
COMPOSE ?= $(shell command -v docker >/dev/null 2>&1 && echo "docker compose" || echo "podman-compose")

ROLE ?= staff
SUB  ?= u1
FILE ?= data/kb/nipoto_kb.json

.PHONY: help install lint fmt test up down logs migrate run keys token kb-import \
        eval-retrieval eval-answers shadow-run check-provider contract-lint

help:  ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install:  ## Install dependencies (incl. dev)
	$(UV) sync

lint:  ## Ruff lint + format check
	$(RUN) ruff check .
	$(RUN) ruff format --check .

fmt:  ## Auto-fix lint and format
	$(RUN) ruff check --fix .
	$(RUN) ruff format .

test:  ## Unit tests (no network). DB tests run only when DATABASE_URL is reachable
	$(RUN) pytest

up:  ## Start postgres + embeddings sidecar (+ app)
	$(COMPOSE) up -d

down:  ## Stop the compose stack
	$(COMPOSE) down

logs:  ## Follow compose logs
	$(COMPOSE) logs -f

migrate:  ## Apply DB migrations
	$(RUN) alembic upgrade head

run:  ## Run the API locally with reload
	$(RUN) uvicorn app.main:app --reload --port 8080

keys:  ## Generate a dev RSA key pair into .keys/
	$(RUN) python scripts/gen_dev_keys.py

token:  ## Mint a dev JWT: make token ROLE=staff SUB=u1
	@$(RUN) python scripts/mint_token.py --role $(ROLE) --sub $(SUB)

kb-import:  ## Import knowledge: make kb-import FILE=data/kb/nipoto_kb.json
	$(RUN) python scripts/kb_import.py $(FILE)

eval-retrieval:  ## Retrieval eval (hit@5, MRR, thresholds) -> evals/reports/
	$(RUN) python evals/run_retrieval.py

eval-answers:  ## Answer eval with a real provider (costs money) -> evals/reports/
	$(RUN) python evals/run_answers.py

shadow-run:  ## Offline shadow batch of the auto pipeline over test conversations
	$(RUN) python jobs/shadow_run.py

check-provider:  ## Validate the LLM provider (stream, JSON mode, usage, TTFT)
	$(RUN) python scripts/check_provider.py

contract-lint:  ## Validate contracts/main-backend.openapi.yaml
	$(RUN) openapi-spec-validator contracts/main-backend.openapi.yaml
