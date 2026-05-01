# Component: Core / Config

> Single source of truth for runtime configuration, loaded from the
> environment via Pydantic Settings.

## Purpose

Centralise every environment-driven setting in one typed place. Code
elsewhere in the backend MUST go through `app.core.config.get_settings()`
and never read `os.environ` directly. This guarantees:

- a single place to document what the service expects in its environment,
- type-checked access (no stringly-typed booleans or ports),
- easy override in tests via `Settings(environment="test", ...)`.

## Public interface

```python
class Settings(BaseSettings):
    environment: Literal["dev", "test", "prod"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    api_host: str
    api_port: int
    cors_origins: list[str]

    anthropic_api_key: str
    model_orchestrator: str
    model_creative_director: str
    model_planner: str
    model_specialist: str
    model_lightweight: str

    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    postgres_db: str

    redis_host: str
    redis_port: int
    redis_db: int

    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_region: str
    s3_bucket_assets: str
    s3_bucket_renders: str
    s3_use_ssl: bool

    # Computed
    database_url: str
    database_url_sync: str
    redis_url: str

def get_settings() -> Settings: ...  # cached
```

## Inputs

Environment variables (lowercased keys). A `.env` file at the repo root
is loaded automatically when present.

## Outputs

A populated `Settings` instance.

## Dependencies

- `pydantic-settings`.

## Errors

`pydantic.ValidationError` raised at startup if a required value cannot be
parsed. Today there are no required values without sensible defaults.

## How to test

Override the cached singleton in tests by constructing
`Settings(environment="test", ...)` and injecting it into FastAPI via
`create_app(settings=...)`.

## Change log notes

- The class extends `BaseSettings`, with `env_nested_delimiter="__"` -
  for nested structures use `FOO__BAR=baz`.
- New settings MUST be added here AND documented in `infra/.env.example`.
