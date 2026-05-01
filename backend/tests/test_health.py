"""Smoke tests for the health endpoints.

The readiness endpoint probes real Postgres / Redis / MinIO and is
therefore covered by integration tests, not by this unit-level suite.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_live_returns_ok(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ai-video-editor-backend"}
