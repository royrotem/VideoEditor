"""initial schema: projects, assets, sessions, messages, edl_versions, render_jobs

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-01

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ASSET_STATUS = sa.Enum("uploaded", "analyzing", "ready", "failed", name="asset_status")
SESSION_STATUS = sa.Enum("active", "closed", name="session_status")
MESSAGE_ROLE = sa.Enum("user", "agent", "system", name="message_role")
JOB_STATUS = sa.Enum("pending", "running", "succeeded", "failed", "cancelled", name="job_status")


def upgrade() -> None:
    bind = op.get_bind()
    ASSET_STATUS.create(bind, checkfirst=True)
    SESSION_STATUS.create(bind, checkfirst=True)
    MESSAGE_ROLE.create(bind, checkfirst=True)
    JOB_STATUS.create(bind, checkfirst=True)

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
    )

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=127), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("s3_bucket", sa.String(length=127), nullable=False),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column("status", ASSET_STATUS, nullable=False),
        sa.Column("analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assets"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name="fk_assets_project_id_projects",
        ),
        sa.UniqueConstraint("s3_bucket", "s3_key", name="uq_assets_bucket_key"),
    )
    op.create_index("ix_assets_project_id", "assets", ["project_id"])

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", SESSION_STATUS, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name="fk_sessions_project_id_projects",
        ),
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", MESSAGE_ROLE, nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            ondelete="CASCADE",
            name="fk_messages_session_id_sessions",
        ),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])

    op.create_table(
        "edl_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("edl", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_edl_versions"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name="fk_edl_versions_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            ondelete="SET NULL",
            name="fk_edl_versions_session_id_sessions",
        ),
        sa.UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_edl_versions_project_version",
        ),
    )

    op.create_table(
        "render_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edl_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", JOB_STATUS, nullable=False),
        sa.Column("output_bucket", sa.String(length=127), nullable=True),
        sa.Column("output_key", sa.String(length=1024), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_render_jobs"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name="fk_render_jobs_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["edl_version_id"],
            ["edl_versions.id"],
            ondelete="CASCADE",
            name="fk_render_jobs_edl_version_id_edl_versions",
        ),
    )
    op.create_index("ix_render_jobs_project_id", "render_jobs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_render_jobs_project_id", table_name="render_jobs")
    op.drop_table("render_jobs")
    op.drop_table("edl_versions")
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_index("ix_assets_project_id", table_name="assets")
    op.drop_table("assets")
    op.drop_table("projects")

    bind = op.get_bind()
    JOB_STATUS.drop(bind, checkfirst=True)
    MESSAGE_ROLE.drop(bind, checkfirst=True)
    SESSION_STATUS.drop(bind, checkfirst=True)
    ASSET_STATUS.drop(bind, checkfirst=True)
