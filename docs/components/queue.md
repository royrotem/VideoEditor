# Component: Queue / Redis

> Async Redis client used as a generic cache today and as the Celery
> broker / result backend in later phases.

## Purpose

One Redis connection per backend process, exposed as an async client.
Long-running media jobs (transcription, scene detection, render) will
run on Celery workers backed by this same Redis instance.

## Public interface

```python
def create_redis_client(settings: Settings) -> Redis: ...
async def redis_health_check(client: Redis) -> None: ...
```

## Inputs

`Settings.redis_host`, `redis_port`, `redis_db`.

## Outputs

A `redis.asyncio.Redis` instance ready to use.

## Dependencies

- `redis` (async client).
- A reachable Redis instance.

## Errors

`redis_health_check` raises :class:`ExternalServiceError` if `PING`
fails.

## How to test

Bring up the `redis` service from `infra/docker-compose.yml`.

## Change log notes

- `decode_responses=False` so binary keys/values are safe by default.
  Decode at the call site when you actually want a string.
