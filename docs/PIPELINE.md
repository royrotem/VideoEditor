# Editing Pipeline

The pipeline is the deterministic, LLM-free part of the system. It accepts
an **Edit Decision List (EDL)** - a Pydantic model produced by the agent
network - and turns it into a rendered video file in object storage.

## Stages

```
ingest → analyze → plan (agents) → validate → render → publish
```

| Stage    | Module                                            | What it does                                                      | Status |
| -------- | ------------------------------------------------- | ----------------------------------------------------------------- | ------ |
| Ingest   | `services/assets.py` (`AssetService.upload`)      | Stores uploaded bytes in MinIO and writes the asset row in Postgres | implemented |
| Analyze (probe) | `pipeline/probe.py` ([doc](components/pipeline/probe.md)) + `services/analysis.py` ([doc](components/services/analysis.md)) | FFprobe — duration, resolution, ``has_audio`` | implemented |
| Analyze (transcribe)  | `pipeline/transcriber.py` ([doc](components/pipeline/transcriber.md)) wired through `services/analysis.py` | Whisper transcript (Hebrew default) | implemented |
| Analyze (qualitative) | `pipeline/frame_extractor.py` ([doc](components/pipeline/frame-extractor.md)) + `agents/vision_analyzer.py` ([doc](components/agents/vision-analyzer.md)), wired through `services/analysis.py` | Sample frames + Hebrew summary + per-shot descriptions | implemented |
| Plan     | `agents/editing_planner.py` + the rest of the agent network | Produces the EDL                                                  | implemented |
| Validate | `pipeline/edl_validator.py` ([doc](components/pipeline/edl-validator.md)) | Structural EDL validation against the project's assets            | implemented |
| Render   | `pipeline/renderer.py` ([doc](components/pipeline/renderer.md)) + `services/render.py` ([doc](components/services/render.md)) | EDL → ffmpeg → MP4 in MinIO | implemented |
| Publish  | (folded into the render service)                  | Updates the render-job row; later: emits a WS event              | partial |

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
