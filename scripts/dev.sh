#!/usr/bin/env bash
# Bring the whole local development environment up:
#   - Postgres / Redis / MinIO via docker compose
#   - apply Alembic migrations
#   - start the FastAPI backend (uvicorn)
#   - start the Next.js frontend
#
# Run from the repository root.  Ctrl-C cleans everything up.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# --- Helpers ---------------------------------------------------------------

# ANSI colours.  Disabled when stdout is not a TTY.
if [[ -t 1 ]]; then
  C_INFO=$'\033[1;34m'; C_WARN=$'\033[1;33m'; C_OK=$'\033[1;32m'; C_RST=$'\033[0m'
else
  C_INFO=""; C_WARN=""; C_OK=""; C_RST=""
fi

info() { printf '%s[dev]%s %s\n' "$C_INFO" "$C_RST" "$*"; }
warn() { printf '%s[dev]%s %s\n' "$C_WARN" "$C_RST" "$*" >&2; }
ok()   { printf '%s[dev]%s %s\n' "$C_OK"   "$C_RST" "$*"; }

# Verify a required binary exists; print a friendly install hint when missing.
require() {
  local bin="$1" hint="$2"
  if ! command -v "$bin" >/dev/null 2>&1; then
    warn "missing binary: $bin"
    warn "  install hint: $hint"
    exit 1
  fi
}

require docker        "https://docs.docker.com/get-docker/"
require uv            "https://docs.astral.sh/uv/getting-started/installation/"
require pnpm          "npm install -g pnpm"
require ffmpeg        "brew install ffmpeg | apt install ffmpeg"
require ffprobe       "ships with ffmpeg"

# --- .env ------------------------------------------------------------------

if [[ ! -f .env ]]; then
  info "no .env at repo root - copying infra/.env.example as a starting point"
  cp infra/.env.example .env
  warn "set ANTHROPIC_API_KEY in .env before using chat / vision endpoints"
fi

# Export the .env so backend + frontend share the values.
set -a
# shellcheck disable=SC1091
source .env
set +a

# --- Infrastructure --------------------------------------------------------

info "bringing up Postgres / Redis / MinIO ..."
docker compose -f infra/docker-compose.yml up -d

# Wait for Postgres to accept connections before running migrations.
info "waiting for Postgres ..."
for _ in {1..30}; do
  if docker compose -f infra/docker-compose.yml exec -T postgres \
        pg_isready -U "${POSTGRES_USER:-videoeditor}" >/dev/null 2>&1; then
    ok "Postgres is ready"
    break
  fi
  sleep 1
done

# --- Migrations ------------------------------------------------------------

info "applying Alembic migrations ..."
(cd backend && uv sync --quiet)
(cd backend && uv run alembic upgrade head)

# --- Backend + frontend (background) --------------------------------------

LOG_DIR="$ROOT/.dev-logs"
mkdir -p "$LOG_DIR"

info "starting backend on http://localhost:${API_PORT:-8000} (logs: $LOG_DIR/backend.log)"
(cd backend && uv run uvicorn app.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --reload) >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

info "installing frontend deps ..."
(cd frontend && pnpm install --silent)

info "starting frontend on http://localhost:3000 (logs: $LOG_DIR/frontend.log)"
(cd frontend && pnpm dev) >"$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

cleanup() {
  info "shutting down ..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  ok "stopped backend + frontend (infra still up - run 'make infra-down' to stop)"
}
trap cleanup EXIT INT TERM

ok "all up. Open http://localhost:3000 (frontend) or http://localhost:8000/health/ready (api)"
ok "tail logs:  tail -f $LOG_DIR/backend.log $LOG_DIR/frontend.log"
ok "press Ctrl-C to stop the dev servers"

# Block until either child exits, then trigger cleanup.
wait -n "$BACKEND_PID" "$FRONTEND_PID"
