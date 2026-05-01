"""FastAPI dependency that yields an :class:`AsyncSession` per request.

Use it as::

    @router.get("/projects")
    async def list_projects(db: AsyncSession = Depends(get_db_session)) -> ...:
        ...

The session is committed at the end of the request when no exception was
raised, otherwise rolled back. The pattern keeps transaction scope tied
to request scope - exactly one transaction per HTTP request.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped :class:`AsyncSession`.

    Reads the session factory built in :func:`app.main.create_app`'s
    lifespan from ``request.app.state``.
    """
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.db_sessionmaker
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
