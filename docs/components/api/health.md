# Component: API / Health

> Liveness and readiness HTTP endpoints used by orchestrators and load
> balancers.

## Purpose

Provide a tiny, dependency-light pair of endpoints that allow operators
to know whether the backend process is up (`/health/live`) and whether
its downstream dependencies are reachable (`/health/ready`).

## Public interface

| Method | Path           | Response                                  |
| ------ | -------------- | ----------------------------------------- |
| GET    | `/health/live` | `HealthStatus` 200                        |
| GET    | `/health/ready`| `ReadinessReport` 200 (ok) or 503 (down)  |

Models live in `backend/app/api/health.py`.

## Inputs

None.

## Outputs

```json
// /health/live
{ "status": "ok", "service": "ai-video-editor-backend" }

// /health/ready (all up)
{
  "status": "ok",
  "database": "ok",
  "redis": "ok",
  "object_store": "ok",
  "errors": {}
}

// /health/ready (something down) - HTTP 503
{
  "status": "down",
  "database": "ok",
  "redis": "down",
  "object_store": "ok",
  "errors": { "redis": "redis unreachable: ..." }
}
```

## Dependencies

- `app.db.engine.health_check` (Postgres).
- `app.queue.redis_client.redis_health_check` (Redis).
- `app.storage.base.ObjectStore.health_check` (MinIO).

## Errors

The endpoint never raises - failures are reported as `down` per
dependency, with the message in `errors`.

## How to test

- Unit: `backend/tests/test_health.py` covers `/health/live`.
- Integration: `/health/ready` requires the docker-compose stack.

## Change log notes

- Probes run sequentially today. If readiness latency becomes a concern,
  switch to `asyncio.gather` for concurrent probing.
