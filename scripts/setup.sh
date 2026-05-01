#!/usr/bin/env bash
# Interactive first-time setup. Idempotent — safe to re-run.
#
#   scripts/setup.sh   # or: make setup
#
# Walks the user through every prerequisite-and-config step before the
# first `make dev`:
#   1. Verify required binaries are installed.
#   2. Bootstrap `.env` from infra/.env.example if missing.
#   3. Prompt for ANTHROPIC_API_KEY when it is unset.
#   4. Bring up Postgres / Redis / MinIO via docker compose.
#   5. Apply Alembic migrations.
#   6. Install backend (uv) + frontend (pnpm) dependencies.
#
# Exit on first error so the user sees exactly what went wrong.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# --- Pretty output ---------------------------------------------------------

if [[ -t 1 ]]; then
  C_INFO=$'\033[1;34m'; C_WARN=$'\033[1;33m'; C_OK=$'\033[1;32m'
  C_ERR=$'\033[1;31m'; C_DIM=$'\033[2m'; C_RST=$'\033[0m'
else
  C_INFO=""; C_WARN=""; C_OK=""; C_ERR=""; C_DIM=""; C_RST=""
fi

step()  { printf '\n%s==>%s %s\n' "$C_INFO" "$C_RST" "$*"; }
ok()    { printf '%s ✓%s %s\n' "$C_OK" "$C_RST" "$*"; }
warn()  { printf '%s !%s %s\n' "$C_WARN" "$C_RST" "$*"; }
fail()  { printf '%s ✗%s %s\n' "$C_ERR" "$C_RST" "$*" >&2; exit 1; }
hint()  { printf '   %s%s%s\n' "$C_DIM" "$*" "$C_RST"; }

# --- 1. Prerequisites ------------------------------------------------------

step "Checking prerequisites"

OS="$(uname -s)"
case "$OS" in
  Darwin) BREW_OR_APT="brew install" ;;
  Linux)  BREW_OR_APT="sudo apt install" ;;
  *)      BREW_OR_APT="(install via your platform's package manager)" ;;
esac

require() {
  local bin="$1" pkg="$2"
  if command -v "$bin" >/dev/null 2>&1; then
    ok "$bin found ($($bin --version 2>&1 | head -1))"
  else
    fail "$bin is missing — install with:  $BREW_OR_APT $pkg"
  fi
}

require docker  docker
require ffmpeg  ffmpeg
require ffprobe ffmpeg
if ! command -v uv >/dev/null 2>&1; then
  fail "uv is missing — install with:  curl -LsSf https://astral.sh/uv/install.sh | sh"
fi
ok "uv found ($(uv --version))"
if ! command -v pnpm >/dev/null 2>&1; then
  fail "pnpm is missing — install with:  npm install -g pnpm"
fi
ok "pnpm found ($(pnpm --version))"

# Docker daemon needs to be running (we'll fail at compose up otherwise,
# but the message is friendlier here).
if ! docker info >/dev/null 2>&1; then
  fail "Docker daemon is not running. Start Docker Desktop / dockerd, then re-run."
fi
ok "Docker daemon is reachable"

# --- 2. .env bootstrap -----------------------------------------------------

step "Bootstrapping .env"

if [[ ! -f .env ]]; then
  cp infra/.env.example .env
  ok "Created .env from infra/.env.example"
else
  ok ".env already exists — leaving it alone"
fi

# --- 3. Anthropic API key ---------------------------------------------------

step "Verifying ANTHROPIC_API_KEY"

# Read current value from the .env (ignore exported shell var on purpose -
# the .env is the source of truth for `make dev`).
current_key="$(grep -E '^ANTHROPIC_API_KEY=' .env | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//')"

if [[ -z "$current_key" ]]; then
  warn "ANTHROPIC_API_KEY is unset in .env."
  hint "Get one at https://console.anthropic.com/settings/keys"
  hint "Press Enter to skip (chat / vision endpoints will fail until set)."
  read -r -p "  Paste your Anthropic API key: " entered_key || entered_key=""
  if [[ -n "$entered_key" ]]; then
    # Replace or append. Mac sed needs an empty `-i` arg; gnu sed doesn't.
    if sed --version >/dev/null 2>&1; then
      sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$entered_key|" .env
    else
      sed -i "" "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$entered_key|" .env
    fi
    ok "Wrote ANTHROPIC_API_KEY to .env"
  else
    warn "Skipped. Edit .env later to add the key."
  fi
else
  ok "ANTHROPIC_API_KEY is set (${current_key:0:8}…)"
fi

# --- 4. Infrastructure -----------------------------------------------------

step "Bringing up Postgres / Redis / MinIO (docker compose)"
docker compose -f infra/docker-compose.yml up -d
ok "Containers started"

# Wait until Postgres is ready before running migrations.
step "Waiting for Postgres to accept connections"
for _ in {1..30}; do
  if docker compose -f infra/docker-compose.yml exec -T postgres \
        pg_isready -U "${POSTGRES_USER:-videoeditor}" >/dev/null 2>&1; then
    ok "Postgres is ready"
    break
  fi
  sleep 1
done

# --- 5. Backend deps + migrations ------------------------------------------

step "Installing backend dependencies (uv sync)"
(cd backend && uv sync --all-extras --dev)
ok "Backend deps installed"

step "Applying Alembic migrations"
(cd backend && uv run alembic upgrade head)
ok "Database schema is up to date"

# --- 6. Frontend deps ------------------------------------------------------

step "Installing frontend dependencies (pnpm install)"
(cd frontend && pnpm install)
ok "Frontend deps installed"

# --- Done ------------------------------------------------------------------

cat <<EOF

${C_OK}Setup complete.${C_RST}

Next steps:
  ${C_INFO}make dev${C_RST}      — start backend + frontend, open http://localhost:3000
  ${C_INFO}make test${C_RST}     — run the full test suite (backend + frontend)
  ${C_INFO}make smoke${C_RST}    — end-to-end smoke against the running stack

In VS Code:
  Open the Command Palette  →  "Tasks: Run Task"  →  "Start dev"
  or use F5 to launch the backend with the debugger attached.

EOF
