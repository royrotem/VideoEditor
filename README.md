# AI Video Editor

עורך וידאו מבוסס AI שמשלב צוות סוכני Claude לעריכת סרטונים מקצה לקצה לפי
תיאור חופשי בשפה טבעית.

> An AI-powered video editor: upload your raw clips, describe what you want
> in plain Hebrew, iterate with a creative-director agent, then let a network
> of specialised Claude agents produce, review, and refine the cut. After the
> first render you can keep editing - manually on a timeline or by asking for
> further changes in words.

## Status

Backend, agent network, and pipeline are end-to-end functional. Frontend
is still a placeholder. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
for the design and [`docs/AGENTS.md`](docs/AGENTS.md) for the agent
catalogue.

## How it works (high level)

1. **Upload** raw video, audio, image assets - the backend probes them
   with `ffprobe`, then asks the Vision Analyzer agent for a Hebrew
   summary plus per-shot descriptions.
2. **Brief** - describe the video you want, in Hebrew.
3. **Iterate** with the Creative Director agent until the plan is
   approved (the agent signals this by starting its closing message
   with `"סיכום:"`).
4. **Plan** - the Brief Extractor distils the chat into a structured
   `BriefPlan`; the Editing Planner turns it into an `EditDecisionList`.
5. **Render** - the EDL Validator catches structural issues; FFmpeg
   produces the file; MinIO holds it; you get a presigned playback URL.
6. **Refine** - request more changes in words, or edit manually
   (frontend tooling pending).

## Prerequisites

You need these on your dev machine:

- Docker (for Postgres / Redis / MinIO via `docker compose`)
- `uv` (Python 3.11 toolchain) - <https://docs.astral.sh/uv/>
- `pnpm` (Node 20+) - `npm install -g pnpm`
- `ffmpeg` and `ffprobe` (used by the probe + frame extractor + renderer)
- An Anthropic API key for the chat / vision endpoints

## One-command run

```bash
make dev
```

Behind the scenes ([`scripts/dev.sh`](scripts/dev.sh)) this:

1. copies `infra/.env.example` → `.env` if missing,
2. brings up Postgres + Redis + MinIO via `docker compose`,
3. waits for Postgres, applies Alembic migrations,
4. starts the FastAPI backend on `:8000`,
5. installs frontend deps and starts the Next.js dev server on `:3000`.

Logs live under `.dev-logs/`. Press <kbd>Ctrl-C</kbd> to stop the dev
servers (infra stays up - run `make infra-down` to stop it).

## Smoke test

Once `make dev` is up, in another terminal:

```bash
make smoke
```

[`scripts/smoke.sh`](scripts/smoke.sh) walks the happy path: liveness
→ create project → generate a 5-second test clip with `ffmpeg` →
upload → open a chat session → submit a tiny EDL for rendering →
fetch the presigned output URL.

Set `SKIP_AGENT=1` to skip the steps that need `ANTHROPIC_API_KEY`.

## Other handy targets

| Target              | What it does                                       |
| ------------------- | -------------------------------------------------- |
| `make infra-up`     | Bring up only Postgres + Redis + MinIO             |
| `make infra-down`   | Stop the docker-compose stack (data preserved)     |
| `make migrate`      | Apply Alembic migrations against the running DB    |
| `make backend-run`  | Run uvicorn in the foreground (no docker-compose)  |
| `make backend-worker` | Run a Celery worker (use with `CELERY_EAGER=false`) |
| `make frontend-run` | Run `next dev` in the foreground                   |
| `make backend-test` | `pytest` against the backend                       |
| `make backend-lint` | `ruff` + `black --check` + `mypy`                  |
| `make test`         | Backend + frontend test suites                     |
| `make clean`        | Remove caches and build outputs                    |

## Repository layout

See [`CLAUDE.md`](CLAUDE.md) for the full layout and the development
rules followed by every contributor (human or agent).

## License

TBD.
