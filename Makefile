# Convenience targets for local development.
#
# Most of these are thin wrappers around the actual tools (uv, pnpm,
# docker compose) so a contributor only needs to know one verb. See
# README.md for the prose version.

.PHONY: help infra-up infra-down infra-logs migrate \
        backend-install backend-run backend-worker backend-test backend-lint \
        frontend-install frontend-run frontend-test \
        dev test smoke clean

help:
	@echo "Common targets:"
	@echo "  make dev               # bring up infra + backend + frontend"
	@echo "  make infra-up          # only Postgres + Redis + MinIO"
	@echo "  make infra-down        # stop containers (data preserved)"
	@echo "  make migrate           # apply Alembic migrations"
	@echo "  make backend-run       # uvicorn (foreground)"
	@echo "  make backend-worker    # Celery worker (foreground)"
	@echo "  make frontend-run      # next dev server (foreground)"
	@echo "  make test              # full test suite (backend + frontend)"
	@echo "  make smoke             # quick end-to-end smoke against running stack"
	@echo "  make clean             # remove caches and build outputs"

# --- Infrastructure ---------------------------------------------------------

infra-up:
	docker compose -f infra/docker-compose.yml up -d
	@echo "Waiting for services to become healthy..."
	@docker compose -f infra/docker-compose.yml ps

infra-down:
	docker compose -f infra/docker-compose.yml down

infra-logs:
	docker compose -f infra/docker-compose.yml logs -f --tail=100

# --- Backend ----------------------------------------------------------------

backend-install:
	cd backend && uv sync --all-extras --dev

migrate:
	cd backend && uv run alembic upgrade head

backend-run:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Celery worker. Set CELERY_EAGER=false in .env (or unset celery_eager) to
# move rendering off the request thread; the worker picks up jobs from
# Redis. Useful for debugging but optional in dev (eager mode by default).
backend-worker:
	cd backend && uv run celery -A app.queue.celery_app:celery_app worker --loglevel=INFO

backend-test:
	cd backend && uv run pytest

backend-lint:
	cd backend && uv run ruff check . && uv run black --check . && uv run mypy app

# --- Frontend ---------------------------------------------------------------

frontend-install:
	cd frontend && pnpm install

frontend-run:
	cd frontend && pnpm dev

frontend-test:
	cd frontend && pnpm test

# --- Composite -------------------------------------------------------------

dev:
	./scripts/dev.sh

test: backend-test frontend-test

smoke:
	./scripts/smoke.sh

clean:
	rm -rf backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache backend/htmlcov
	rm -rf frontend/.next frontend/.turbo frontend/node_modules
