# Architecture

This document is the single source of truth for the high-level design of
the AI Video Editor. Update it whenever an architectural boundary changes.

## Goals

- Translate a free-text Hebrew brief plus user-uploaded assets into a
  rendered video, through an iterative dialogue with the user.
- Keep video-domain reasoning (creative direction, EDL planning, QA) in
  Claude agents; keep deterministic media work (cuts, encoding) in a
  dedicated processing pipeline.
- Allow further edits after the first render, both in plain Hebrew and via a
  manual timeline.

## High-level diagram

```
                +-------------------------+
                |  Frontend (Next.js, RTL)|
                |  upload • chat • editor |
                +-----------+-------------+
                            |
                       REST / WebSocket
                            |
                +-----------v-------------+
                |  Backend API (FastAPI)  |
                |  auth • sessions • jobs |
                +-----+-------+-----------+
                      |       |
            +---------+       +----------+
            |                            |
   +--------v---------+         +--------v----------+
   | Agent Orchestr.  |         | Storage & DB      |
   | (Claude SDK)     |         | MinIO / Postgres  |
   +--------+---------+         +-------------------+
            |
            |  delegates to specialists (Vision,
            |  Creative Director, Planner, Cut,
            |  Audio, Color, Subtitles, QA)
            v
   +------------------+         +-------------------+
   | EDL (JSON)       +-------->+ Render Pipeline   |
   |                  |         | FFmpeg / MoviePy  |
   +------------------+         +---------+---------+
                                          |
                                  rendered video to MinIO
```

## Core boundaries

### 1. Frontend (`frontend/`)
A Next.js 15 App Router application configured for RTL Hebrew. Owns:
- file upload UX, brief input, chat with the Creative Director,
- preview & approval of editing plans,
- timeline editor for manual edits,
- a "request a change in words" affordance after render.

### 2. Backend API (`backend/app/api/`)
FastAPI service that exposes:
- project / asset / job CRUD,
- a streaming chat endpoint that proxies to the agent orchestrator,
- a render endpoint that enqueues a render job,
- WebSocket events for progress.

### 3. Agent Network (`backend/app/agents/`)
A directed network of Claude-backed agents coordinated by an Orchestrator.
Each agent is a small module exporting a callable plus its system prompt.
See [`AGENTS.md`](AGENTS.md) for the full catalogue.

The agent network communicates through a typed message bus (in-process for
now; can be swapped for Redis pub/sub later). All inter-agent data is
**Pydantic models** - no free-form dicts crossing agent boundaries.

### 4. Pipeline (`backend/app/pipeline/`)
Pure media-processing code. Takes an EDL (Edit Decision List, a Pydantic
model) and produces a rendered file in MinIO. No LLM calls live here.
See [`PIPELINE.md`](PIPELINE.md).

### 5. Storage (`backend/app/storage/`)
Abstract `ObjectStore` interface. The concrete implementation is MinIO
(S3-compatible). The same interface is used in dev, test, and production -
test backend uses a MinIO test container.

### 6. Database (`backend/app/db/`)
PostgreSQL via SQLAlchemy 2 + Alembic. Tables: `projects`, `assets`,
`sessions`, `messages`, `edl_versions`, `render_jobs`.

### 7. Queue (`backend/app/queue/`)
Celery on Redis. Long-running jobs (transcription, scene detection,
rendering) run as Celery tasks; the API stays async-friendly.

## Data flow for one editing session

1. User creates a **Project**, uploads **Assets** (stored in MinIO,
   metadata in Postgres).
2. Backend kicks off **Vision Analyzer** + **Audio transcription** jobs;
   results stored alongside each asset.
3. User opens a chat **Session** with the **Creative Director** agent and
   describes the desired video.
4. Creative Director iterates with the user; when the user approves,
   it asks the **Editing Planner** to emit an **EDL** (versioned).
5. Specialist agents (Cut / Audio / Color / Subtitles) refine the EDL.
6. **QA Reviewer** checks the EDL against the brief; loops back if needed.
7. The pipeline renders the EDL to MinIO; frontend gets a WebSocket
   completion event with the playback URL.
8. User can:
   - request changes in words → Creative Director updates the EDL → re-render,
   - or edit the EDL manually on the timeline → re-render.

## Non-goals (for now)

- Multi-user collaboration on the same project.
- Real-time collaborative editing.
- Mobile-first UI.
- On-device rendering.

## Configuration

All runtime configuration is in environment variables, loaded by Pydantic
Settings. See `infra/.env.example`.
