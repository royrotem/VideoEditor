"""Object storage adapters.

The :class:`ObjectStore` protocol defines the interface used everywhere
in the codebase. The concrete implementation is :class:`S3ObjectStore`,
backed by MinIO in dev/test and a real S3 in production.
"""

from app.storage.base import ObjectStore, StoredObject
from app.storage.s3 import S3ObjectStore

__all__ = ["ObjectStore", "StoredObject", "S3ObjectStore"]
