"""RFC 9457 problem+json errors with a stable `code` field (§5.1)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

CONTENT_TYPE = "application/problem+json"

# Stable machine-readable codes. Endpoints must reuse these, never invent ad-hoc strings.
DEFAULT_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "invalid_request",
    429: "rate_limited",
    500: "internal_error",
    502: "upstream_unavailable",
    503: "unavailable",
    504: "upstream_timeout",
}


class AppError(Exception):
    """Base class for errors that render as problem+json."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    title: str = "Internal Server Error"

    def __init__(
        self,
        detail: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail or self.title)
        self.detail = detail
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.extra = extra or {}


def problem_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str | None = None,
    detail: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title or code.replace("_", " ").title(),
        "status": status_code,
        "code": code,
        "instance": request.url.path,
    }
    if detail:
        body["detail"] = detail
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        body["request_id"] = request_id
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status_code, media_type=CONTENT_TYPE)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return problem_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            extra=exc.extra,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = DEFAULT_CODES.get(exc.status_code, "http_error")
        detail = exc.detail if isinstance(exc.detail, str) else None
        return problem_response(request, status_code=exc.status_code, code=code, detail=detail)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem_response(
            request,
            status_code=422,
            code="invalid_request",
            detail="Request validation failed.",
            extra={"errors": _safe_errors(exc)},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Detail is deliberately generic: internals never leak to the caller.
        return problem_response(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            detail="An unexpected error occurred.",
        )


def _safe_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """Validation errors without the offending input, which may hold customer text."""
    out = []
    for err in exc.errors():
        out.append(
            {
                "loc": [str(p) for p in err.get("loc", ())],
                "msg": err.get("msg"),
                "type": err.get("type"),
            }
        )
    return out
