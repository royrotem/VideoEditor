# Editing Pipeline

The pipeline is the deterministic, LLM-free part of the system. It accepts
an **Edit Decision List (EDL)** - a Pydantic model produced by the agent
network - and turns it into a rendered video file in object storage.

## Stages

```
ingest → analyze → plan (agents) → assemble → render → publish
```

| Stage     | Module                           | What it does                                              |
| --------- | -------------------------------- | --------------------------------------------------------- |
| Ingest    | `pipeline/ingest.py`             | Validates uploads, probes with FFprobe, stores in MinIO   |
| Analyze   | `pipeline/analyze.py`            | Scene detection, transcription (Whisper), shot tagging    |
| Plan      | (handled by agent network)       | Produces the EDL                                          |
| Assemble  | `pipeline/assemble.py`           | Resolves EDL clips to physical files, builds a MoviePy graph |
| Render    | `pipeline/render.py`             | Encodes via FFmpeg, writes to MinIO                       |
| Publish   | `pipeline/publish.py`            | Records render artifact in DB, emits WS event             |

## EDL format

The EDL is defined in `backend/app/pipeline/edl.py` as a Pydantic model.
Top-level shape:

```python
class EditDecisionList(BaseModel):
    version: int
    timeline: list[Track]
    audio: AudioPlan
    subtitles: SubtitlePlan | None
    color: ColorPlan | None
    output: OutputSpec  # resolution, fps, format
```

The full schema is documented in
[`components/pipeline/edl.md`](components/pipeline/edl.md).

## Job execution

Long-running stages (analyze, render) run as Celery tasks. The API enqueues
the job and returns a `job_id`; the frontend subscribes to a WebSocket
channel `jobs:<id>` to receive progress and completion events.

## Failure model

- Each stage is idempotent on `(project_id, edl_version)`.
- Any stage that fails records the error against the render job and emits
  a `job.failed` event. The QA agent can be invoked to suggest a fix.
- Partial outputs (e.g. half-rendered file) are deleted on failure - we do
  not leave dangling artifacts in MinIO.
