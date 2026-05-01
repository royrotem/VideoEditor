# Component: Services / AssetAnalysisService

> Orchestrates the analysis stages on a stored asset: download bytes
> from MinIO, run a :class:`Probe`, optionally extract sample frames
> and run the Vision Analyzer agent for a Hebrew summary + per-shot
> descriptions, persist everything into ``assets.analysis``, flip
> the asset's ``status``.

## Purpose

Bridge :class:`Probe` (a pure function) to the rest of the system
(database, object store). Routes never call :class:`Probe` directly;
they call this service.

The service runs inline today as part of the upload flow (see
``POST /projects/{id}/assets``); it is also exposed standalone via
``POST /projects/{id}/assets/{asset_id}/analyze`` so users can
re-analyse after a probe upgrade or after an earlier failure.

## Flow

```
analyze(asset_id)
  ├── assets.get(asset_id)             # 404 if unknown
  ├── status = analyzing                # transitional
  ├── tempfile.mkdtemp(prefix="probe-")
  ├── object_store.get(asset.s3_bucket, asset.s3_key)
  ├── write bytes to local scratch
  ├── probe.probe(local_path)
  │     ├── on AppError → status=failed, analysis={"error": ...}, return
  │     └── on success  → merge probe facts into analysis
  ├── (optional) vision pass — best-effort:
  │     ├── if frame_extractor and llm and duration_seconds > 0:
  │     │     ├── frame_extractor.extract(local_path, count=N, duration=...)
  │     │     ├── VisionAnalyzer(llm).run_with_frames(facts, frames)
  │     │     └── merge {summary, shots} into analysis
  │     └── any AppError here is logged as a warning, NOT propagated —
  │         the deterministic half is still saved
  ├── status = ready
  └── shutil.rmtree(scratch)            # always
```

The method does **not** raise on probe failure - the outcome is
fully reflected in the returned :class:`Asset` row, so the route can
return the same shape for success and failure.

## Public interface

```python
class AssetAnalysisService:
    async def analyze(self, asset_id: UUID) -> Asset: ...
```

## What it writes to ``asset.analysis``

The probe contributes:

| Key                  | Source                               |
| -------------------- | ------------------------------------ |
| `duration_seconds`   | :class:`ProbeResult`                 |
| `width`              | :class:`ProbeResult`                 |
| `height`             | :class:`ProbeResult`                 |
| `has_audio`          | :class:`ProbeResult`                 |
| `container_format`   | :class:`ProbeResult`                 |

The Vision Analyzer (when wired in) adds:

| Key        | Source                                         |
| ---------- | ---------------------------------------------- |
| `summary`  | :class:`VisionAnalysisOutput.summary`          |
| `shots`    | :class:`VisionAnalysisOutput.shots` (JSON list)|

Keys outside that set are preserved by the merge step. Re-running
either pass alone does not blow away the other half.

## Dependencies

- :class:`Probe` (default :class:`FFprobeProbe`).
- :class:`FrameExtractor` (default :class:`FFmpegFrameExtractor`,
  optional - vision pass is skipped silently if absent).
- :class:`LLMClient` (default :class:`AnthropicLLMClient`, optional
  - same).
- :class:`ObjectStore` (production: :class:`S3ObjectStore`).
- :class:`AssetRepository`.

## Errors

| Caller-visible exception | When                                |
| ------------------------ | ----------------------------------- |
| :class:`AssetNotFoundError` | The asset id does not exist     |

Probe failures surface on the returned :class:`Asset`
(``status = failed``, ``analysis["error"]`` populated) - not as
exceptions.

## How to test

- ``backend/tests/test_analysis_service.py`` covers happy path,
  probe-raises → status flips to failed, prior-analysis preservation
  on re-probe, and unknown-asset.
- Route-level: see ``test_routes_projects.py`` for the upload-then-
  reanalyze paths.

## Change log notes

- The probe runs **inline** during upload today. Moving it to a
  Celery worker is a one-line swap: build a Celery task that takes
  ``asset_id``, calls the same ``analyze`` method, and updates the
  row from the worker process. The route stays the same; clients
  just observe ``status = analyzing`` for longer.
- Scratch directories are removed on every exit path; partial
  downloads are never observable to other components.
