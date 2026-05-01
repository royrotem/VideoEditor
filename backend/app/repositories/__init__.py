"""Thin data-access layer.

Each repository encapsulates SQLAlchemy queries for one aggregate root
so service code stays free of select/insert mechanics.
"""

from app.repositories.assets import AssetRepository
from app.repositories.projects import ProjectRepository
from app.repositories.render_jobs import EdlVersionRepository, RenderJobRepository
from app.repositories.sessions import MessageRepository, SessionRepository

__all__ = [
    "AssetRepository",
    "EdlVersionRepository",
    "MessageRepository",
    "ProjectRepository",
    "RenderJobRepository",
    "SessionRepository",
]
