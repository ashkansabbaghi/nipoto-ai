"""T1.6: the CI definition. A YAML typo here is only noticed on the next push, so the
things that matter are asserted locally."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CI_FILE = ROOT / ".gitlab-ci.yml"


@pytest.fixture(scope="module")
def ci() -> dict[str, Any]:
    return yaml.safe_load(CI_FILE.read_text(encoding="utf-8"))


def jobs(ci: dict[str, Any]) -> dict[str, dict[str, Any]]:
    reserved = {"include", "stages", "variables", "default", "workflow"}
    return {
        name: body
        for name, body in ci.items()
        if name not in reserved and not name.startswith(".") and isinstance(body, dict)
    }


def resolve(ci: dict[str, Any], job: dict[str, Any], key: str) -> Any:
    """Read a key, following a single level of `extends`."""
    if key in job:
        return job[key]
    parent = job.get("extends")
    if isinstance(parent, str):
        return resolve(ci, ci[parent], key)
    return None


def test_every_job_uses_a_declared_stage(ci: dict[str, Any]) -> None:
    declared = set(ci["stages"])
    for name, job in jobs(ci).items():
        stage = resolve(ci, job, "stage")
        assert stage in declared, f"{name} uses undeclared stage {stage!r}"


def test_lint_runs_the_same_checks_as_make_lint(ci: dict[str, Any]) -> None:
    script = " ".join(ci["lint"]["script"])
    assert "ruff check" in script
    assert "ruff format --check" in script


def test_tests_run_against_a_real_postgres(ci: dict[str, Any]) -> None:
    """Without DATABASE_URL the `db` tests skip, and the schema would go untested."""
    test_job = ci["test"]
    images = [str(service.get("name", service)) for service in test_job["services"]]
    resolved = [ci["variables"].get(image.lstrip("$"), image) for image in images]
    assert any("pgvector" in image for image in resolved)
    url = test_job["variables"]["DATABASE_URL"]
    assert url.startswith("postgresql+asyncpg://")
    assert "@db:" in url  # matches the service alias


def test_tests_do_not_call_a_real_provider(ci: dict[str, Any]) -> None:
    variables = ci["test"]["variables"]
    assert variables["LLM_PROVIDER"] == "fake"
    assert variables["MAIN_BACKEND"] == "fake"


def test_eval_is_manual_and_scoped(ci: dict[str, Any]) -> None:
    """It costs money, so it must never run automatically."""
    eval_job = ci["eval"]
    assert eval_job["when"] == "manual"
    rule = eval_job["rules"][0]
    assert rule["when"] == "manual"
    assert set(rule["changes"]) == {
        "app/pipeline/prompts/**/*",
        "config/routes.yaml",
        "app/retrieval/**/*",
    }
    assert eval_job["rules"][-1] == {"when": "never"}


def test_the_contract_is_validated_in_ci(ci: dict[str, Any]) -> None:
    assert "openapi-spec-validator" in " ".join(ci["contract"]["script"])


def test_a_merge_request_never_publishes_latest(ci: dict[str, Any]) -> None:
    script = " ".join(ci["build_mr"]["script"])
    assert "$LATEST_TAG" not in script.replace("--cache-from $LATEST_TAG", "")
    assert "mr-$CI_MERGE_REQUEST_IID" in ci["build_mr"]["variables"]["VERSION_TAG"]


def test_release_build_only_runs_on_a_tag(ci: dict[str, Any]) -> None:
    assert ci["build"]["rules"] == [{"if": "$CI_COMMIT_TAG"}]
