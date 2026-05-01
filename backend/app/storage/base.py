"""Storage abstraction.

All callers depend on the :class:`ObjectStore` protocol; concrete
implementations live in sibling modules. Keeping the interface tiny makes
it easy to swap MinIO for any other S3-compatible backend, and keeps the
test surface small.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(slots=True, frozen=True)
class StoredObject:
    """Reference to an object in the store.

    Attributes:
        bucket: The bucket the object lives in.
        key: The object key (path) within the bucket.
        size_bytes: Object size in bytes; ``None`` if unknown.
        content_type: MIME type, when known.
    """

    bucket: str
    key: str
    size_bytes: int | None = None
    content_type: str | None = None


class ObjectStore(Protocol):
    """Async object storage interface.

    Every method either succeeds or raises a subclass of
    :class:`app.core.errors.ExternalServiceError` so callers can handle
    storage failures uniformly.
    """

    async def put(
        self,
        bucket: str,
        key: str,
        data: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> StoredObject:
        """Upload ``data`` to ``bucket/key`` and return its descriptor."""

    async def get(self, bucket: str, key: str) -> bytes:
        """Download the object at ``bucket/key`` and return its bytes."""

    async def delete(self, bucket: str, key: str) -> None:
        """Delete the object at ``bucket/key`` (no-op if it is missing)."""

    async def exists(self, bucket: str, key: str) -> bool:
        """Return whether ``bucket/key`` exists."""

    async def presigned_get_url(self, bucket: str, key: str, *, ttl_seconds: int) -> str:
        """Return a time-limited URL the caller can fetch the object from."""

    async def health_check(self) -> None:
        """Verify the store is reachable; raise on failure."""
