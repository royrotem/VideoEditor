# Component: Services / AssetAnalysisService

> Orchestrates the deterministic analysis stage on a stored asset:
> download bytes from MinIO, run a :class:`Probe`, persist the
> result into ``assets.analysis``, flip the asset's ``status``.

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
  │     ├── on AppError → status=failed, analysis={"error": ...}
  │     └── on success  → merge probe facts into analysis, status=ready
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

| Key                  | Source field on :class:`ProbeResult` |
| -------------------- | ------------------------------------ |
| `duration_seconds`   | `duration_seconds`                   |
| `width`              | `width`                              |
| `height`             | `height`                             |
| `has_audio`          | `has_audio`                          |
| `container_format`   | `container_format`                   |

Keys outside that set (``shots``, ``transcript``, ``summary``,
anything the Vision Analyzer agent writes later) are preserved by
the merge step. Re-running the probe alone will not blow away
qualitative facts.

## Dependencies

- :class:`Probe` (default :class:`FFprobeProbe`).
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
