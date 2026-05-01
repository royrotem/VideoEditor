# Component: Storage / Object Store

> S3-compatible object storage used to hold raw uploaded assets and the
> rendered videos.

## Purpose

Persist binary blobs (video, audio, image files, rendered outputs) under
a stable bucket+key naming scheme. Callers depend on the abstract
:class:`ObjectStore` protocol so the same code works against MinIO in
dev/test and managed S3 in production.

## Public interface

```python
class ObjectStore(Protocol):
    async def put(self, bucket, key, data, *, content_type=None) -> StoredObject: ...
    async def get(self, bucket, key) -> bytes: ...
    async def delete(self, bucket, key) -> None: ...
    async def exists(self, bucket, key) -> bool: ...
    async def presigned_get_url(self, bucket, key, *, ttl_seconds) -> str: ...
    async def health_check(self) -> None: ...

class S3ObjectStore(ObjectStore): ...  # boto3 implementation
```

## Inputs

- `bucket: str` - one of `Settings.s3_bucket_assets`, `Settings.s3_bucket_renders`.
- `key: str` - opaque object key (we use UUID-based keys).
- `data: BinaryIO` - any seekable binary stream for `put`.

## Outputs

- :class:`StoredObject` (`bucket`, `key`, `size_bytes`, `content_type`).
- `bytes` for `get`.
- A presigned URL string for `presigned_get_url`.

## Dependencies

- `boto3`, `botocore` (sync, wrapped via `asyncio.to_thread`).
- Settings: `s3_endpoint_url`, `s3_access_key`, `s3_secret_key`,
  `s3_region`, `s3_use_ssl`.
- The `assets` and `renders` buckets, created by the `minio-bootstrap`
  service in `infra/docker-compose.yml`.

## Errors

| Error                  | When                                        | Caller action               |
| ---------------------- | ------------------------------------------- | --------------------------- |
| `ExternalServiceError` | network failure, auth failure, bucket gone  | bubble up; readiness 503    |

## How to test

- Unit: mock the protocol via a fake implementation in tests.
- Integration: hit the MinIO container brought up by docker-compose.

## Change log notes

- The protocol stays minimal on purpose. Resist adding S3-specific
  options (versioning, lifecycle) - put those behind dedicated methods so
  alternate backends remain trivial to write.
