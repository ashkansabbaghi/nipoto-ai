"""T1.4: policy.yaml, routes.yaml and startup validation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.policy import (
    ConfigError,
    Policy,
    Routes,
    expand_env,
    load_policy,
    load_routes,
)
from app.main import create_app

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def policy() -> Policy:
    return load_policy(REPO / "config" / "policy.yaml")


@pytest.fixture
def routes(monkeypatch) -> Routes:
    monkeypatch.setenv("CHAT_MODEL", "test-chat")
    monkeypatch.setenv("SMALL_MODEL", "test-small")
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("LLM_API_KEY", "k")
    return load_routes(REPO / "config" / "routes.yaml")


# --- the shipped files ----------------------------------------------------------


def test_repo_policy_is_valid(policy: Policy) -> None:
    assert policy.company_name
    assert policy.deny_topics
    assert policy.limits.turns_per_conversation > 0
    assert policy.limits.daily_budget_usd > 0


def test_repo_routes_are_valid(routes: Routes) -> None:
    assert set(routes.routes) == {"draft.generate", "auto.generate", "router.classify"}
    assert routes.embedding.dim == 1024  # must match kb_chunks.embedding
    assert routes.reranker.enabled is False  # D8: rerank is post-MVP


def test_env_placeholders_are_substituted(routes: Routes) -> None:
    assert routes.route("draft.generate").model == "test-chat"
    assert routes.route("router.classify").model == "test-small"
    assert routes.providers["main"].base_url == "https://provider.example/v1"


def test_unset_env_placeholder_becomes_none(monkeypatch) -> None:
    monkeypatch.delenv("CHAT_MODEL", raising=False)
    loaded = load_routes(REPO / "config" / "routes.yaml")
    assert loaded.route("draft.generate").model is None
    with pytest.raises(ConfigError, match="CHAT_MODEL"):
        loaded.require_models()


def test_expand_env_is_recursive(monkeypatch) -> None:
    monkeypatch.setenv("X", "value")
    assert expand_env({"a": ["${X}", "pre-${X}-post"], "b": {"c": "${X}"}}) == {
        "a": ["value", "pre-value-post"],
        "b": {"c": "value"},
    }


# --- link allowlist -------------------------------------------------------------


@pytest.mark.parametrize(
    ("host", "allowed"),
    [
        ("nipoto.com", True),
        ("help.nipoto.com", True),
        ("a.b.help.nipoto.com", True),
        ("NIPOTO.COM", True),
        ("nipoto.com.evil.com", False),
        ("evilnipoto.com", False),
        ("evil.com", False),
        ("", False),
    ],
)
def test_link_allowlist_matching(policy: Policy, host: str, allowed: bool) -> None:
    assert policy.allows_host(host) is allowed


# --- invalid files stop startup -------------------------------------------------


def _write(tmp_path: Path, name: str, data: object) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_missing_file_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_policy(tmp_path / "nope.yaml")


def test_malformed_yaml_is_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text("company_name: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_policy(path)


def test_policy_missing_a_required_key_is_rejected(tmp_path: Path, policy: Policy) -> None:
    data = policy.model_dump()
    del data["deny_topics"]
    with pytest.raises(ConfigError, match="deny_topics"):
        load_policy(_write(tmp_path, "policy.yaml", data))


def test_policy_with_an_unknown_key_is_rejected(tmp_path: Path, policy: Policy) -> None:
    """A typo must not silently disable a control."""
    data = policy.model_dump()
    data["deny_topics_typo"] = ["x"]
    with pytest.raises(ConfigError, match="deny_topics_typo"):
        load_policy(_write(tmp_path, "policy.yaml", data))


def test_link_allowlist_rejects_a_url(tmp_path: Path, policy: Policy) -> None:
    data = policy.model_dump()
    data["link_allowlist"] = ["https://nipoto.com/help"]
    with pytest.raises(ConfigError, match="bare hosts"):
        load_policy(_write(tmp_path, "policy.yaml", data))


def test_zero_budget_is_rejected(tmp_path: Path, policy: Policy) -> None:
    data = policy.model_dump()
    data["limits"]["daily_budget_usd"] = 0
    with pytest.raises(ConfigError):
        load_policy(_write(tmp_path, "policy.yaml", data))


def test_thresholds_must_be_ordered(tmp_path: Path, routes: Routes) -> None:
    data = routes.model_dump()
    data["thresholds"] = {"t_low": 0.8, "t_high": 0.4}
    with pytest.raises(ConfigError, match="t_low"):
        load_routes(_write(tmp_path, "routes.yaml", data))


def test_route_pointing_at_an_unknown_provider_is_rejected(tmp_path: Path, routes: Routes) -> None:
    data = routes.model_dump()
    data["routes"]["draft.generate"]["provider"] = "ghost"
    with pytest.raises(ConfigError, match="ghost"):
        load_routes(_write(tmp_path, "routes.yaml", data))


def test_a_missing_route_is_rejected(tmp_path: Path, routes: Routes) -> None:
    data = routes.model_dump()
    del data["routes"]["router.classify"]
    with pytest.raises(ConfigError, match=r"router\.classify"):
        load_routes(_write(tmp_path, "routes.yaml", data))


# --- startup --------------------------------------------------------------------


def test_invalid_policy_stops_startup(tmp_path: Path) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text("company_name: only-this", encoding="utf-8")
    settings = Settings(env="test", policy_file=bad, _env_file=None)  # type: ignore[call-arg]
    with pytest.raises(ConfigError):
        create_app(settings)


def test_real_provider_without_a_model_stops_startup(monkeypatch) -> None:
    monkeypatch.delenv("CHAT_MODEL", raising=False)
    monkeypatch.delenv("SMALL_MODEL", raising=False)
    settings = Settings(env="test", llm_provider="openai_compat", _env_file=None)  # type: ignore[call-arg]
    with pytest.raises(ConfigError, match="CHAT_MODEL"):
        create_app(settings)


def test_fake_provider_starts_without_a_model(monkeypatch) -> None:
    monkeypatch.delenv("CHAT_MODEL", raising=False)
    settings = Settings(env="test", llm_provider="fake", _env_file=None)  # type: ignore[call-arg]
    with TestClient(create_app(settings)) as client:
        assert client.get("/v1/health").status_code == 200


def test_policy_and_routes_are_on_app_state(client: TestClient) -> None:
    assert client.app.state.policy.company_name
    assert client.app.state.routes.route("auto.generate").max_tokens > 0
