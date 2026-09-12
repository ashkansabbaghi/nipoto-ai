"""Typed models for config/policy.yaml and config/routes.yaml (§13, §10.3).

Both files are validated at startup; an invalid file stops the process with a clear
message rather than failing later on a request.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

CONFIG_DIR = Path("config")
_ENV_REF = re.compile(r"\$\{([A-Z0-9_]+)\}")


class ConfigError(RuntimeError):
    """A policy or routes file is missing or invalid."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- policy.yaml ----------------------------------------------------------------


class Contact(Strict):
    phone: str
    hours: str


class Limits(Strict):
    turns_per_conversation: int = Field(gt=0)
    daily_budget_usd: float = Field(gt=0)
    requests_per_minute_per_actor: int = Field(default=20, gt=0)
    requests_per_minute_per_ip: int = Field(default=60, gt=0)


class LanguagePolicy(Strict):
    expected: str = "fa"
    min_persian_ratio: float = Field(default=0.5, ge=0, le=1)


class Policy(Strict):
    company_name: str
    persona: str
    deny_topics: list[str]
    link_allowlist: list[str]
    contact: Contact
    limits: Limits
    language: LanguagePolicy = LanguagePolicy()

    @field_validator("link_allowlist")
    @classmethod
    def _hosts_only(cls, hosts: list[str]) -> list[str]:
        for host in hosts:
            if "/" in host or ":" in host:
                raise ValueError(f"link_allowlist takes bare hosts, got {host!r}")
        return [host.lower() for host in hosts]

    def allows_host(self, host: str) -> bool:
        """True for an allowlisted host or any of its subdomains."""
        host = host.lower().rstrip(".")
        return any(
            host == allowed or host.endswith("." + allowed) for allowed in self.link_allowlist
        )


# --- routes.yaml ----------------------------------------------------------------

ROUTE_NAMES = ("draft.generate", "auto.generate", "router.classify")


class Provider(Strict):
    base_url: str | None = None
    api_key: str | None = None


class Route(Strict):
    provider: str
    # None while the model is still being chosen (T0.3). `require_models()` rejects that
    # at startup for any provider other than `fake`.
    model: str | None = None
    max_tokens: int = Field(gt=0)
    temperature: float = Field(ge=0, le=2)
    timeout_s: float = Field(gt=0)


class EmbeddingConfig(Strict):
    model: str
    device: str = "cpu"
    dim: int = Field(default=1024, gt=0)


class RerankerConfig(Strict):
    model: str
    enabled: bool = False


class Thresholds(Strict):
    """§9.9. `t_low` < `t_high`; both are set on the golden set in T2.7."""

    t_low: float
    t_high: float

    @model_validator(mode="after")
    def _ordered(self) -> Thresholds:
        if not self.t_low < self.t_high:
            raise ValueError(f"t_low ({self.t_low}) must be below t_high ({self.t_high})")
        return self


class Price(Strict):
    """USD per 1M tokens."""

    input: float = Field(ge=0)
    output: float = Field(ge=0)


class Routes(Strict):
    providers: dict[str, Provider]
    routes: dict[str, Route]
    embedding: EmbeddingConfig
    reranker: RerankerConfig
    thresholds: Thresholds
    pricing: dict[str, Price] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _routes_are_complete(self) -> Routes:
        missing = [name for name in ROUTE_NAMES if name not in self.routes]
        if missing:
            raise ValueError(f"routes.yaml is missing required routes: {', '.join(missing)}")
        for name, route in self.routes.items():
            if route.provider not in self.providers:
                raise ValueError(f"route {name!r} points at unknown provider {route.provider!r}")
        return self

    def route(self, name: str) -> Route:
        try:
            return self.routes[name]
        except KeyError:
            raise ConfigError(f"Unknown route {name!r}") from None

    def price(self, model: str) -> Price | None:
        return self.pricing.get(model)

    def require_models(self) -> None:
        """Every route must name a model before a real provider is used."""
        missing = [name for name, route in self.routes.items() if not route.model]
        if missing:
            raise ConfigError(
                "No model configured for route(s): "
                + ", ".join(sorted(missing))
                + ". Set CHAT_MODEL and SMALL_MODEL (T0.3), or run with LLM_PROVIDER=fake."
            )


# --- loading --------------------------------------------------------------------


def expand_env(value: Any) -> Any:
    """Replace `${VAR}` with the environment value, recursively. Unset vars become None
    (a whole-value reference) or an empty string (inside a larger string)."""
    if isinstance(value, str):
        match = _ENV_REF.fullmatch(value)
        if match:
            return os.environ.get(match.group(1)) or None
        return _ENV_REF.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {key: expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_env(item) for item in value]
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    return data


def load_policy(path: Path | None = None) -> Policy:
    path = path or CONFIG_DIR / "policy.yaml"
    try:
        return Policy.model_validate(_load_yaml(path))
    except ValidationError as exc:
        raise ConfigError(f"{path} is invalid:\n{exc}") from exc


def load_routes(path: Path | None = None) -> Routes:
    path = path or CONFIG_DIR / "routes.yaml"
    try:
        return Routes.model_validate(expand_env(_load_yaml(path)))
    except ValidationError as exc:
        raise ConfigError(f"{path} is invalid:\n{exc}") from exc
