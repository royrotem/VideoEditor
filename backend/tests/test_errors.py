"""Tests for the API error translation layer."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_error_handlers
from app.core.errors import AssetNotFoundError


def test_app_error_is_translated_to_structured_response() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def _boom() -> None:
        raise AssetNotFoundError("asset 'foo' is missing")

    response = TestClient(app).get("/boom")

    assert response.status_code == 404
    body = response.json()
    assert body == {
        "error": {
            "code": "asset.not_found",
            "message": "asset 'foo' is missing",
        }
    }
