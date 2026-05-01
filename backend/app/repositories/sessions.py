"""SQLAlchemy queries for the ``sessions`` and ``messages`` tables."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.db.enums import MessageRole, SessionStatus
from app.db.models import Message, Session


class SessionRepository:
    """Data-access for chat :class:`~app.db.models.Session`."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def create(self, *, project_id: UUID) -> Session:
        chat = Session(project_id=project_id, status=SessionStatus.ACTIVE)
        self._db.add(chat)
        await self._db.flush()
        return chat

    async def get(self, session_id: UUID) -> Session:
        chat = await self._db.get(Session, session_id)
        if chat is None:
            raise NotFoundError(f"session {session_id} not found")
        return chat

    async def get_with_messages(self, session_id: UUID) -> Session:
        result = await self._db.execute(
            select(Session)
            .where(Session.id == session_id)
            .options(selectinload(Session.messages))
        )
        chat = result.scalar_one_or_none()
        if chat is None:
            raise NotFoundError(f"session {session_id} not found")
        return chat

    async def list_for_project(self, project_id: UUID) -> list[Session]:
        result = await self._db.execute(
            select(Session)
            .where(Session.project_id == project_id)
            .order_by(Session.created_at.desc())
        )
        return list(result.scalars())

    async def close(self, session_id: UUID) -> Session:
        chat = await self.get(session_id)
        chat.status = SessionStatus.CLOSED
        await self._db.flush()
        return chat


class MessageRepository:
    """Data-access for chat :class:`~app.db.models.Message`."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def append(
        self,
        *,
        session_id: UUID,
        role: MessageRole,
        content: str,
        agent_name: str | None = None,
    ) -> Message:
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            agent_name=agent_name,
        )
        self._db.add(message)
        await self._db.flush()
        return message

    async def list_for_session(self, session_id: UUID) -> list[Message]:
        result = await self._db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars())
