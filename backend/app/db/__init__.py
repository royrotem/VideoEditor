"""Database layer (SQLAlchemy 2 + asyncpg).

Only schema, sessions, and migrations live here. Business logic must
import from the application services, not directly from this package.
"""

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.engine import create_engine_and_sessionmaker, dispose_engine, health_check
from app.db.session import get_db_session

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPKMixin",
    "create_engine_and_sessionmaker",
    "dispose_engine",
    "get_db_session",
    "health_check",
]
