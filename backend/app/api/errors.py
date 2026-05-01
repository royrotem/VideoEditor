"""FastAPI exception handlers that translate :class:`AppError` to HTTP."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import AppError


def _error_response(error: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=error.http_status,
        content={"error": {"code": error.code, "message": error.message}},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach the application's error handlers to ``app``."""

    @app.exception_handler(AppError)
    async def _on_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc)
