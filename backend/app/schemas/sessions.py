"""API schemas for the ``sessions`` and ``messages`` resources."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import MessageRole, SessionStatus


class SessionRead(BaseModel):
    """Representation of a chat session in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    status: SessionStatus
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    """Representation of a single chat turn."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    role: MessageRole
    agent_name: str | None
    content: str
    created_at: datetime


class UserTurn(BaseModel):
    """Body of ``POST /sessions/{id}/messages`` - one user turn in."""

    content: str = Field(min_length=1, max_length=8192)


class AssistantReply(BaseModel):
    """Returned when the user posts a turn.

    Contains the new user message that was appended, the assistant
    reply, and a flag indicating whether the Creative Director marked
    its closing summary (``"סיכום:"``) - that's the signal for the
    frontend to invite the user to confirm and proceed to planning.
    """

    user_message: MessageRead
    assistant_message: MessageRead
    converged: bool
