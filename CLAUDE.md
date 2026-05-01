# CLAUDE.md - Development Guide for AI Agents

This file is read by Claude Code and other AI development agents working on this
repository. It defines how to navigate, develop, and document the project.

## Project Summary

**AI Video Editor** - a multi-agent application powered by Claude that takes
user-uploaded video assets and a natural-language brief, iteratively proposes
editing ideas, executes the approved plan, and lets the user request further
edits in plain language or via a manual timeline.

The user interface is **Hebrew (RTL)**. Source code, identifiers, comments,
docs, and commit messages are **English**.

## Repository Layout

```
VideoEditor/
├── CLAUDE.md                  # this file - developer agent guide
├── README.md                  # human-facing project overview
├── docs/                      # component & architecture documentation
│   ├── ARCHITECTURE.md        # high-level architecture
│   ├── AGENTS.md              # catalogue of every Claude agent
│   ├── PIPELINE.md            # end-to-end editing pipeline
│   ├── COMPONENT_TEMPLATE.md  # template for new component docs
│   └── components/            # one .md per component
├── backend/                   # Python / FastAPI backend
│   ├── app/
│   │   ├── agents/            # Claude agent definitions
│   │   ├── pipeline/          # video processing pipeline
│   │   ├── api/               # FastAPI routes
│   │   ├── storage/           # MinIO / S3 adapter
│   │   ├── db/                # Postgres models & migrations
│   │   ├── queue/             # Redis / Celery jobs
│   │   └── core/              # config, logging, errors
│   └── tests/
├── frontend/                  # Next.js + TypeScript frontend (RTL Hebrew)
├── skills/                    # video-editing skills loaded at runtime
├── infra/                     # docker-compose, env templates
└── .github/workflows/         # CI
```

## Tech Stack (locked in)

- **Backend**: Python 3.11, FastAPI, Pydantic v2, Anthropic SDK, MoviePy,
  FFmpeg, Whisper (transcription), Celery + Redis (job queue),
  SQLAlchemy 2 + Alembic.
- **Frontend**: Next.js 15 (App Router), React 19, TypeScript, TailwindCSS,
  shadcn/ui, RTL configuration.
- **Storage**: MinIO (S3-compatible) - used both in dev and prod.
- **DB**: PostgreSQL 16. **Cache/Queue**: Redis 7.
- **Tests**: pytest (+ pytest-asyncio) for backend, vitest + Playwright for
  frontend.
- **Lint/Format**: ruff + black + mypy (backend), eslint + prettier (frontend).

## Workflow Rules

1. **Branch per feature.** Branch off the active development branch
   (currently `claude/ai-video-editor-2oB1U`). Naming: `feature/<slug>`,
   `fix/<slug>`, `docs/<slug>`, `refactor/<slug>`.
2. **Small, descriptive commits** using Conventional Commits in English
   (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
3. **Update docs in the same commit.** Any code change that affects a
   component MUST update its matching `docs/components/<name>.md` so the
   docs never drift.
4. **Tests required** for new business logic. A feature is "done" only when
   its tests pass and its component doc is up to date.
5. **No half-finished features merged.** If you can't finish, leave it on
   the feature branch.

## Documentation Rules

- Every component (agent, pipeline stage, API module, frontend feature)
  has a doc in `docs/components/<name>.md` that follows
  `docs/COMPONENT_TEMPLATE.md`.
- Component docs describe **purpose, public interface, dependencies, data
  contracts, error modes, and how to test it**. They do not duplicate the
  source code - they make it discoverable.
- `docs/ARCHITECTURE.md` is the single source of truth for the high-level
  picture. Update it whenever an architectural boundary changes.
- `docs/AGENTS.md` lists every Claude agent: role, model, system prompt
  location, inputs, outputs, and which other agents it talks to.

## Clean Code Principles (non-negotiable)

- **Single responsibility.** One module, one reason to change.
- **Dependency injection** for models, storage, queues - never hard-code.
- **Type-safe everywhere.** `mypy --strict` on backend, `tsc --noEmit` on
  frontend.
- **Descriptive names.** No abbreviations except well-known ones (`id`,
  `url`, `db`).
- **Small functions.** If a function does not fit on one screen, split it.
- **No dead code.** Delete unused code; do not leave commented-out blocks.
- **Comments explain WHY, not WHAT.** Code says what; comments say why.
- **Boundaries validated, internals trusted.** Validate at API and external
  service edges only.

## Local Development

The fastest path is `make dev`, which runs `scripts/dev.sh`:

```bash
make dev               # infra + migrations + backend + frontend, in one terminal
make smoke             # end-to-end sanity check against a running stack
```

Individual targets (also documented in `make help`):

```bash
make infra-up          # Postgres + Redis + MinIO via docker compose
make migrate           # alembic upgrade head
make backend-run       # uvicorn --reload, foreground
make frontend-run      # next dev, foreground
make test              # backend + frontend test suites
```

Manual equivalents are still valid:

```bash
docker compose -f infra/docker-compose.yml up -d
(cd backend && uv sync && uv run alembic upgrade head)
(cd backend && uv run uvicorn app.main:app --reload)
(cd frontend && pnpm install && pnpm dev)
```

## When You Are Asked To Make A Change

1. Read the relevant `docs/components/*.md` first - it is the contract.
2. Make the change, write tests, update the doc, run lint+tests.
3. Commit with a Conventional Commit message.
4. Open a feature branch if not already on one.
