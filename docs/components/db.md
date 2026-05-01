# Component: Database

> SQLAlchemy 2 async engine + session factory bound to PostgreSQL 16.

> See also: [`db-schema.md`](db-schema.md) for the table layout and
> [`db-migrations.md`](db-migrations.md) for Alembic.

## Purpose

Own the database connection pool. Every other module gets database
access through the session factory (`async_sessionmaker[AsyncSession]`),
never by holding the engine directly.

## Public interface

```python
def create_engine_and_sessionmaker(settings: Settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]: ...
async def dispose_engine(engine: AsyncEngine) -> None: ...
async def health_check(engine: AsyncEngine) -> None: ...

# FastAPI dependency, request-scoped session with auto commit/rollback
async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]: ...
```

## Inputs

`Settings.database_url` (DSN built from the postgres_* env vars).

## Outputs

- `(engine, sessionmaker)` tuple.
- `health_check` returns ``None`` on success.

## Dependencies

- `sqlalchemy[asyncio]`, `asyncpg` (runtime), `psycopg[binary]` (Alembic).
- A reachable Postgres instance.

## Errors

`health_check` raises :class:`ExternalServiceError` if the database is
unreachable. Other call sites surface SQLAlchemy errors normally.

## How to test

- Bring up the `postgres` service from `infra/docker-compose.yml`.
- Integration tests will run against that container in a future phase.

## Change log notes

- Pool sized for a single backend process (10 + 20 overflow). Adjust
  before scaling horizontally.
- Migrations are managed by Alembic; see
  [`db-migrations.md`](db-migrations.md). They use the synchronous DSN
  exposed by `Settings.database_url_sync`.
