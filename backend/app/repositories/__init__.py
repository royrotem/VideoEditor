"""Thin data-access layer.

Each repository encapsulates SQLAlchemy queries for one aggregate root
so service code stays free of select/insert mechanics.
"""

from app.repositories.assets import AssetRepository
from app.repositories.projects import ProjectRepository

__all__ = ["AssetRepository", "ProjectRepository"]
