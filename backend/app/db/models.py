"""ORM models for the AI Video Editor.

Tables:

- ``projects`` - one editing project per user-uploaded video idea.
- ``assets`` - raw uploaded files (video, audio, image) attached to a project.
- ``sessions`` - chat sessions between the user and the agent network.
- ``messages`` - one row per turn in a session.
- ``edl_versions`` - immutable, versioned snapshots of the Edit Decision List.
- ``render_jobs`` - one row per attempt to render an EDL into a video file.

Status fields use string enums (declared in :mod:`app.db.enums`) so the
database schema stays human-readable and diffable.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.enums import (
    AssetStatus,
    JobStatus,
    MessageRole,
    SessionStatus,
)


class Project(Base, UUIDPKMixin, TimestampMixin):
    """A single video-editing project owned by a user."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    assets: Mapped[list["Asset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    edl_versions: Mapped[list["EdlVersion"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    render_jobs: Mapped[list["RenderJob"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Asset(Base, UUIDPKMixin, TimestampMixin):
    """A raw file uploaded by the user (video, audio, image).

    The bytes live in MinIO at ``s3://{s3_bucket}/{s3_key}``; ``analysis``
    holds whatever the Vision Analyzer / transcription stages produced
    for this asset (shape defined per pipeline stage).
    """

    __tablename__ = "assets"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(127), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    s3_bucket: Mapped[str] = mapped_column(String(127), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(
        SAEnum(AssetStatus, name="asset_status"),
        nullable=False,
        default=AssetStatus.UPLOADED,
    )
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB(), nullable=True)

    project: Mapped[Project] = relationship(back_populates="assets")

    __table_args__ = (
        UniqueConstraint("s3_bucket", "s3_key", name="uq_assets_bucket_key"),
        Index("ix_assets_project_id", "project_id"),
    )


class Session(Base, UUIDPKMixin, TimestampMixin):
    """A chat session between a user and the Creative Director agent."""

    __tablename__ = "sessions"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[SessionStatus] = mapped_column(
        SAEnum(SessionStatus, name="session_status"),
        nullable=False,
        default=SessionStatus.ACTIVE,
    )

    project: Mapped[Project] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base, UUIDPKMixin, TimestampMixin):
    """One turn inside a :class:`Session`.

    ``agent_name`` is set when ``role == AGENT`` and identifies which
    agent in the network produced the turn (e.g. ``creative_director``).
    """

    __tablename__ = "messages"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, name="message_role"), nullable=False
    )
    agent_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(Text(), nullable=False)

    session: Mapped[Session] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_messages_session_id", "session_id"),)


class EdlVersion(Base, UUIDPKMixin, TimestampMixin):
    """An immutable, versioned snapshot of an Edit Decision List.

    The ``edl`` column stores the full :class:`EditDecisionList` Pydantic
    model serialized as JSON. Versions within a project are numbered
    starting at 1 and are never overwritten - amendments produce a new
    row.
    """

    __tablename__ = "edl_versions"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer(), nullable=False)
    edl: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False)
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="edl_versions")

    __table_args__ = (
        UniqueConstraint(
            "project_id", "version_number", name="uq_edl_versions_project_version"
        ),
    )


class RenderJob(Base, UUIDPKMixin, TimestampMixin):
    """One attempt to render an :class:`EdlVersion` into a video file.

    The output (when ``status == SUCCEEDED``) lives at
    ``s3://{output_bucket}/{output_key}``.
    """

    __tablename__ = "render_jobs"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    edl_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("edl_versions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status"),
        nullable=False,
        default=JobStatus.PENDING,
    )
    output_bucket: Mapped[str | None] = mapped_column(String(127), nullable=True)
    output_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)

    project: Mapped[Project] = relationship(back_populates="render_jobs")

    __table_args__ = (Index("ix_render_jobs_project_id", "project_id"),)
