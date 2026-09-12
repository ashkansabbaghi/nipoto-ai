"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health
from app.connectors import build_backend
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.core.policy import load_policy, load_routes
from app.db.session import dispose_engine, init_engine

API_PREFIX = "/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    init_engine(settings)  # lazy: no connection is opened until the first query
    app.state.backend = build_backend(settings)
    get_logger("app").info("startup", env=settings.env, version=__version__)
    yield
    await app.state.backend.aclose()
    await dispose_engine()
    get_logger("app").info("shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    # Fail fast: an invalid policy or routes file stops startup with a clear message,
    # rather than surfacing on the first request (T1.4).
    policy = load_policy(settings.policy_file)
    routes = load_routes(settings.routes_file)
    if settings.llm_provider != "fake":
        routes.require_models()

    app = FastAPI(
        title="nipoto-ai",
        version=__version__,
        description="Nipoto AI support service: knowledge search, staff drafts and auto replies.",
        lifespan=lifespan,
        # Docs stay off in production; /openapi.json is the contract for the front-end teams.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.policy = policy
    app.state.routes = routes

    app.add_middleware(RequestContextMiddleware)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,  # never "*" (§5.1)
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
            expose_headers=["X-Request-Id"],
        )

    install_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    return app


app = create_app()
