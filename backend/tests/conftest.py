"""Shared pytest fixtures for the backend test suite."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Test-scoped settings overriding the cached singleton."""
    return Settings(environment="test")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """A FastAPI :class:`TestClient` wired to a fresh app instance."""
    app = create_app(settings=settings)
    with TestClient(app) as test_client:
        yield test_client
