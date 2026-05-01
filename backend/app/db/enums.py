"""String enums used by ORM models.

We declare them as Python ``StrEnum`` subclasses so the database column
holds the human-readable string (e.g. ``"uploaded"``) and so they
serialize naturally to JSON.
"""

from __future__ import annotations

from enum import StrEnum


class AssetStatus(StrEnum):
    """Lifecycle of a single :class:`~app.db.models.Asset`."""

    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    READY = "ready"
    FAILED = "failed"


class SessionStatus(StrEnum):
    """Lifecycle of a chat :class:`~app.db.models.Session`."""

    ACTIVE = "active"
    CLOSED = "closed"


class MessageRole(StrEnum):
    """Producer of a :class:`~app.db.models.Message` turn."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class JobStatus(StrEnum):
    """Lifecycle of a long-running job (rendering, analysis)."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
