"""HTTP routes for chat sessions and the Brief Extractor."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from app.agents.contracts import BriefPlan
from app.api.deps import ChatServiceDep
from app.schemas.sessions import (
    AssistantReply,
    MessageRead,
    SessionRead,
    UserTurn,
)

router = APIRouter(tags=["sessions"])


class StartSessionBody(BaseModel):
    """Body of ``POST /projects/{id}/sessions``."""

    brief: str = Field(min_length=1, max_length=8192)


class StartSessionResponse(BaseModel):
    """Returned when a chat session is opened.

    Includes the Director's first reply so the client can render the
    chat without an extra round trip.
    """

    session: SessionRead
    user_message: MessageRead
    assistant_message: MessageRead


@router.post(
    "/projects/{project_id}/sessions",
    response_model=StartSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_session(
    body: StartSessionBody,
    service: ChatServiceDep,
    project_id: UUID = Path(...),
) -> StartSessionResponse:
    chat_session, user_message, assistant_message = await service.start_session(
        project_id=project_id, brief=body.brief
    )
    return StartSessionResponse(
        session=SessionRead.model_validate(chat_session),
        user_message=MessageRead.model_validate(user_message),
        assistant_message=MessageRead.model_validate(assistant_message),
    )


@router.get(
    "/projects/{project_id}/sessions",
    response_model=list[SessionRead],
)
async def list_sessions(
    service: ChatServiceDep,
    project_id: UUID = Path(...),
) -> list[SessionRead]:
    rows = await service.list_sessions(project_id)
    return [SessionRead.model_validate(s) for s in rows]


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[MessageRead],
)
async def list_messages(
    service: ChatServiceDep,
    session_id: UUID = Path(...),
) -> list[MessageRead]:
    rows = await service.list_messages(session_id)
    return [MessageRead.model_validate(m) for m in rows]


@router.post(
    "/sessions/{session_id}/messages",
    response_model=AssistantReply,
    status_code=status.HTTP_201_CREATED,
)
async def send_turn(
    body: UserTurn,
    service: ChatServiceDep,
    session_id: UUID = Path(...),
) -> AssistantReply:
    user_message, assistant_message, converged = await service.send_turn(
        session_id=session_id, content=body.content
    )
    return AssistantReply(
        user_message=MessageRead.model_validate(user_message),
        assistant_message=MessageRead.model_validate(assistant_message),
        converged=converged,
    )


@router.post(
    "/sessions/{session_id}/extract-brief",
    response_model=BriefPlan,
)
async def extract_brief(
    service: ChatServiceDep,
    session_id: UUID = Path(...),
) -> BriefPlan:
    """Run the Brief Extractor over the full session transcript.

    Called once the chat has converged (the Director's reply starts
    with ``"סיכום:"``). Returns the structured :class:`BriefPlan` ready
    to be passed to the Editing Planner.
    """
    return await service.extract_brief(session_id=session_id)
