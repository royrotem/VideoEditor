# AI Video Editor

עורך וידאו מבוסס AI שמשלב צוות סוכני Claude לעריכת סרטונים מקצה לקצה לפי
תיאור חופשי בשפה טבעית.

> An AI-powered video editor: upload your raw clips, describe what you want
> in plain Hebrew, iterate with a creative-director agent, then let a network
> of specialised Claude agents produce, review, and refine the cut. After the
> first render you can keep editing - manually on a timeline or by asking for
> further changes in words.

## Status

Under active development. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
for the design and [`docs/AGENTS.md`](docs/AGENTS.md) for the agent network.

## How it works (high level)

1. **Upload** raw video, audio, image assets.
2. **Brief** - describe the video you want, in Hebrew.
3. **Iterate** with the Creative Director agent until the plan is approved.
4. **Render** - the agent network produces an Edit Decision List (EDL),
   the pipeline executes it with FFmpeg / MoviePy.
5. **Refine** - request more changes in words, or edit manually.

## Quick start

```bash
# Start local infrastructure (Postgres + Redis + MinIO)
docker compose -f infra/docker-compose.yml up -d

# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
pnpm install
pnpm dev
```

Open http://localhost:3000.

## Repository layout

See [`CLAUDE.md`](CLAUDE.md) for the full layout and development rules
followed by every contributor (human or agent).

## License

TBD.
