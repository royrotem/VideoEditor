"""SQLAlchemy declarative base shared by every ORM model.

We pin a deterministic naming convention for indexes / constraints so
Alembic can autogenerate stable, diff-friendly migrations. Timestamps
are timezone-aware and primary keys are UUIDs by default.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Project-wide declarative base.

    Every model inherits from :class:`Base` so Alembic discovers it via
    :attr:`Base.metadata`.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPKMixin:
    """Mixin that adds a UUID primary key column named ``id``.

    The default is generated client-side so we know the value before
    flushing - useful for emitting events that reference the new row.
    """

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)


class TimestampMixin:
    """Mixin that adds timezone-aware ``created_at`` / ``updated_at``.

    ``created_at`` is set on insert; ``updated_at`` is bumped on every
    write via the database's ``now()`` function.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
