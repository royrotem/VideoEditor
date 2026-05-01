# Component: API / Assets

> Upload and list raw asset files (video / audio / image) attached to a
> project.

## Purpose

Move user-uploaded bytes into MinIO and record metadata in Postgres in
a single transactional step. Provide a presigned URL so the frontend
can render a preview without round-tripping the bytes through the API.

## Public interface

| Method | Path                                                   | Body / Query             | Response               |
| ------ | ------------------------------------------------------ | ------------------------ | ---------------------- |
| POST   | `/projects/{project_id}/assets`                        | multipart `file`         | `AssetCreated` 201     |
| POST   | `/projects/{project_id}/assets/{asset_id}/analyze`     | -                        | `AssetRead` 200        |
| GET    | `/projects/{project_id}/assets`                        | -                        | `list[AssetRead]`      |
| GET    | `/projects/{project_id}/assets/{asset_id}/url`         | `ttl_seconds`            | `{ url, ttl_seconds }` |

Schemas live in `backend/app/schemas/assets.py`. The upload route
runs the deterministic probe stage inline before responding, so the
returned asset reports its post-analysis state (``ready`` or
``failed``) and ``analysis`` carries duration / resolution /
``has_audio`` ready for the Validator and the Creative Director.
The dedicated ``/analyze`` route re-runs the probe on demand.

## Storage layout

Object keys are built as `{project_id}/{upload_uuid}/{filename}`,
written to the bucket configured by `Settings.s3_bucket_assets`. The
per-upload UUID guarantees uniqueness even for duplicate filenames.

## Dependencies

- `AssetService` (`app.services.assets`) for orchestration.
- `AssetRepository`, `ProjectRepository` for persistence.
- `ObjectStore` (MinIO via `S3ObjectStore`).

## Errors

| Error                           | When                              | HTTP |
| ------------------------------- | --------------------------------- | ---- |
| `resource.not_found`            | Project does not exist            | 404  |
| `asset.not_found`               | Asset id is unknown               | 404  |
| `external.failed`               | MinIO upload / presign failed     | 502  |

## How to test

- Unit: `backend/tests/test_asset_service.py` against in-memory fakes.
- HTTP: `backend/tests/test_routes_projects.py` exercises the routes
  with FastAPI dependency overrides.
- Integration (future): real MinIO + Postgres from
  `infra/docker-compose.yml`.

## Change log notes

- The TTL for the immediately-returned `preview_url` is one hour. The
  GET-presign endpoint accepts a TTL between 60 s and 24 h.
- We do **not** validate file content types beyond what the browser
  sends. Content sniffing / restriction lives in a separate component
  (Vision Analyzer) when it inspects the asset.
