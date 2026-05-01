"""Static checks against the ORM metadata.

These tests verify the model layer is wired correctly without needing
a live database. End-to-end migration / CRUD coverage will live under
``tests/integration/`` and run against the docker-compose Postgres.
"""

from __future__ import annotations

from app.db.base import Base
from app.db.enums import AssetStatus, JobStatus, MessageRole, SessionStatus
from app.db.models import (
    Asset,
    EdlVersion,
    Message,
    Project,
    RenderJob,
    Session,
)

EXPECTED_TABLES = {
    "projects",
    "assets",
    "sessions",
    "messages",
    "edl_versions",
    "render_jobs",
}


def test_metadata_contains_every_expected_table() -> None:
    actual = set(Base.metadata.tables.keys())
    assert EXPECTED_TABLES.issubset(actual)


def test_project_has_expected_relationships() -> None:
    relationships = {rel.key for rel in Project.__mapper__.relationships}
    assert relationships == {"assets", "sessions", "edl_versions", "render_jobs"}


def test_asset_unique_constraint_on_bucket_key() -> None:
    constraints = {c.name for c in Asset.__table__.constraints}
    assert "uq_assets_bucket_key" in constraints


def test_edl_version_unique_constraint_on_project_version() -> None:
    constraints = {c.name for c in EdlVersion.__table__.constraints}
    assert "uq_edl_versions_project_version" in constraints


def test_message_role_enum_values() -> None:
    assert {role.value for role in MessageRole} == {"user", "agent", "system"}


def test_status_enum_values() -> None:
    assert {s.value for s in AssetStatus} == {"uploaded", "analyzing", "ready", "failed"}
    assert {s.value for s in SessionStatus} == {"active", "closed"}
    assert {s.value for s in JobStatus} == {
        "pending",
        "running",
        "succeeded",
        "failed",
        "cancelled",
    }


def test_models_use_uuid_primary_keys() -> None:
    for model in (Project, Asset, Session, Message, EdlVersion, RenderJob):
        pk_columns = [c.name for c in model.__table__.primary_key.columns]
        assert pk_columns == ["id"], f"{model.__name__} should have a single 'id' PK"


def test_naming_convention_applied_to_indexes() -> None:
    index_names = {idx.name for idx in Asset.__table__.indexes}
    assert "ix_assets_project_id" in index_names
