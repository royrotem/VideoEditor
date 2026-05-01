"""S3-compatible :class:`ObjectStore` implementation, used with MinIO.

We use ``boto3`` synchronously and run blocking calls in a worker thread
via ``asyncio.to_thread`` to keep the interface async without needing an
async S3 library.
"""

from __future__ import annotations

import asyncio
from typing import BinaryIO

import boto3
from botocore.client import BaseClient
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.storage.base import ObjectStore, StoredObject


class S3ObjectStore(ObjectStore):
    """:class:`ObjectStore` backed by an S3-compatible service (MinIO).

    The same code path runs in dev (against MinIO from the docker-compose
    stack) and in production (against managed S3) - only the endpoint and
    credentials change.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: BaseClient = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_use_ssl,
            config=BotoConfig(signature_version="s3v4"),
        )

    async def put(
        self,
        bucket: str,
        key: str,
        data: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> StoredObject:
        extra_args: dict[str, str] = {}
        if content_type is not None:
            extra_args["ContentType"] = content_type

        def _upload() -> None:
            self._client.upload_fileobj(data, bucket, key, ExtraArgs=extra_args or None)

        try:
            await asyncio.to_thread(_upload)
            head = await asyncio.to_thread(self._client.head_object, Bucket=bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise ExternalServiceError(f"failed to put s3://{bucket}/{key}: {exc}") from exc

        return StoredObject(
            bucket=bucket,
            key=key,
            size_bytes=head.get("ContentLength"),
            content_type=head.get("ContentType") or content_type,
        )

    async def get(self, bucket: str, key: str) -> bytes:
        try:
            obj = await asyncio.to_thread(self._client.get_object, Bucket=bucket, Key=key)
            return await asyncio.to_thread(obj["Body"].read)
        except (BotoCoreError, ClientError) as exc:
            raise ExternalServiceError(f"failed to get s3://{bucket}/{key}: {exc}") from exc

    async def delete(self, bucket: str, key: str) -> None:
        try:
            await asyncio.to_thread(self._client.delete_object, Bucket=bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise ExternalServiceError(f"failed to delete s3://{bucket}/{key}: {exc}") from exc

    async def exists(self, bucket: str, key: str) -> bool:
        try:
            await asyncio.to_thread(self._client.head_object, Bucket=bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                return False
            raise ExternalServiceError(f"failed to head s3://{bucket}/{key}: {exc}") from exc

    async def presigned_get_url(self, bucket: str, key: str, *, ttl_seconds: int) -> str:
        try:
            return await asyncio.to_thread(
                self._client.generate_presigned_url,
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )
        except (BotoCoreError, ClientError) as exc:
            raise ExternalServiceError(f"failed to presign s3://{bucket}/{key}: {exc}") from exc

    async def health_check(self) -> None:
        try:
            await asyncio.to_thread(self._client.list_buckets)
        except (BotoCoreError, ClientError) as exc:
            raise ExternalServiceError(f"object store unreachable: {exc}") from exc
