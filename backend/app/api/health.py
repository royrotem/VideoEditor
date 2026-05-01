"""Liveness and readiness endpoints.

- ``/health/live`` returns 200 as long as the process is up.
- ``/health/ready`` probes Postgres, Redis, and MinIO and reports each
  dependency's status. It returns 200 only when every probe succeeds.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.db.engine import health_check as db_health_check
from app.queue.redis_client import redis_health_check
from app.storage.base import ObjectStore

router = APIRouter(prefix="/health", tags=["health"])
log = get_logger("api.health")


class HealthStatus(BaseModel):
    """Body returned by ``/health/live``."""

    status: str
    service: str = "ai-video-editor-backend"


class ReadinessReport(BaseModel):
    """Per-dependency readiness report.

    A dependency is "ok" when its probe succeeds, otherwise "down" plus a
    short error message. The top-level ``status`` is "ok" only when every
    dependency is "ok".
    """

    status: str
    database: str
    redis: str
    object_store: str
    errors: dict[str, str] = {}


@router.get("/live", response_model=HealthStatus)
async def live() -> HealthStatus:
    """Process liveness check."""
    return HealthStatus(status="ok")


@router.get("/ready", response_model=ReadinessReport)
async def ready(request: Request, response: Response) -> ReadinessReport:
    """Readiness check that probes every infrastructure dependency."""
    errors: dict[str, str] = {}

    db_status = await _probe(
        "database",
        lambda: db_health_check(request.app.state.db_engine),
        errors,
    )
    redis_status = await _probe(
        "redis",
        lambda: redis_health_check(request.app.state.redis),
        errors,
    )
    store: ObjectStore = request.app.state.object_store
    store_status = await _probe("object_store", store.health_check, errors)

    overall = "ok" if not errors else "down"
    if errors:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessReport(
        status=overall,
        database=db_status,
        redis=redis_status,
        object_store=store_status,
        errors=errors,
    )


async def _probe(name: str, probe, errors: dict[str, str]) -> str:  # type: ignore[no-untyped-def]
    """Run ``probe`` and translate exceptions into the error map.

    Kept tiny on purpose - this helper exists only so the readiness route
    reads as a flat list of dependency probes.
    """
    try:
        await probe()
    except ExternalServiceError as exc:
        log.warning("health.dependency_down", name=name, error=str(exc))
        errors[name] = exc.message
        return "down"
    except Exception as exc:  # noqa: BLE001 - unexpected, surface but don't crash
        log.exception("health.dependency_error", name=name)
        errors[name] = str(exc)
        return "down"
    return "ok"
