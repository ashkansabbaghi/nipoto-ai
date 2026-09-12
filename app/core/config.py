"""Application settings, loaded from the environment (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Env = Literal["development", "test", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    env: Env = "development"
    log_level: str = "INFO"
    log_json: bool = False
    # NoDecode: the value in .env is a comma-separated list, not JSON.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    database_url: str = "postgresql+asyncpg://nipoto:nipoto@localhost:5433/nipoto_ai"

    jwt_audience: str = "nipoto-ai"
    jwt_public_key_file: str | None = None
    jwt_private_key_file: str | None = None
    jwks_url: str | None = None

    main_backend: Literal["fake", "http"] = "fake"
    main_backend_url: str | None = None
    main_backend_token: str | None = None
    fake_backend_dir: str = "data/fixtures/conversations"

    llm_provider: Literal["fake", "openai_compat"] = "fake"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    chat_model: str | None = None
    small_model: str | None = None

    embedder: Literal["fake", "openai_compat"] = "fake"
    embeddings_base_url: str = "http://localhost:8081/v1"
    embeddings_model: str = "BAAI/bge-m3"
    embeddings_api_key: str | None = None

    demo_enabled: bool = True

    policy_file: Path = Path("config/policy.yaml")
    routes_file: Path = Path("config/routes.yaml")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string, as used in .env."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("log_level")
    @classmethod
    def _upper_level(cls, value: str) -> str:
        return value.upper()

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
