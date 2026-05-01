"""Chat use cases.

Coordinates the Creative Director agent, the message store, and (when
the conversation converges) the Brief Extractor. Routes call into this
service so HTTP handlers stay thin.
"""

from __future__ import annotations

from uuid import UUID

from app.agents.brief_extractor import (
    BriefExtractor,
    ConversationTranscript,
    LLMMessageDict,
)
from app.agents.client import LLMClient, LLMMessage
from app.agents.contracts import AssetFacts, BriefPlan
from app.agents.creative_director import CreativeDirector, is_approval_message
from app.core.errors import ValidationError
from app.db.enums import MessageRole, SessionStatus
from app.db.models import Message, Session
from app.repositories.assets import AssetRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sessions import MessageRepository, SessionRepository


class ChatService:
    """Owns one chat session's interaction with the agent network."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        projects: ProjectRepository,
        assets: AssetRepository,
        sessions: SessionRepository,
        messages: MessageRepository,
    ) -> None:
        self._llm = llm
        self._projects = projects
        self._assets = assets
        self._sessions = sessions
        self._messages = messages

    async def start_session(self, *, project_id: UUID, brief: str) -> tuple[Session, Message, Message]:
        """Open a new chat session and run the Director's first reply.

        Returns ``(session, opening_user_message, assistant_message)``.
        The opening user message carries the brief plus the asset
        facts (so the Director cannot hallucinate footage); only the
        ``brief`` argument is shown to the user.
        """
        if not brief.strip():
            raise ValidationError("brief must not be empty")

        await self._projects.get(project_id)
        chat_session = await self._sessions.create(project_id=project_id)

        asset_facts = await self._collect_asset_facts(project_id)
        opening = CreativeDirector.build_opening_user_message(
            brief=brief, asset_facts=asset_facts
        )

        user_message = await self._messages.append(
            session_id=chat_session.id,
            role=MessageRole.USER,
            content=opening.content,
        )

        director = CreativeDirector(self._llm)
        reply = await director.reply([opening])
        assistant_message = await self._messages.append(
            session_id=chat_session.id,
            role=MessageRole.AGENT,
            agent_name=CreativeDirector.name,
            content=reply,
        )
        return chat_session, user_message, assistant_message

    async def send_turn(
        self, *, session_id: UUID, content: str
    ) -> tuple[Message, Message, bool]:
        """Append a user turn, get the Director's reply, persist both.

        Returns ``(user_message, assistant_message, converged)``. The
        ``converged`` flag is true when the Director's reply starts
        with the approval marker (``"סיכום:"``).
        """
        if not content.strip():
            raise ValidationError("message content must not be empty")

        chat_session = await self._sessions.get(session_id)
        if chat_session.status is SessionStatus.CLOSED:
            raise ValidationError("session is closed")

        history = await self._messages.list_for_session(session_id)
        history_for_llm = [
            LLMMessage(role=_role_for_llm(m.role), content=m.content) for m in history
        ]
        history_for_llm.append(LLMMessage(role="user", content=content))

        user_message = await self._messages.append(
            session_id=session_id, role=MessageRole.USER, content=content
        )

        director = CreativeDirector(self._llm)
        reply = await director.reply(history_for_llm)
        assistant_message = await self._messages.append(
            session_id=session_id,
            role=MessageRole.AGENT,
            agent_name=CreativeDirector.name,
            content=reply,
        )

        converged = is_approval_message(reply)
        if converged:
            await self._sessions.close(session_id)

        return user_message, assistant_message, converged

    async def extract_brief(self, *, session_id: UUID) -> BriefPlan:
        """Run the Brief Extractor over the full session transcript."""
        chat_session = await self._sessions.get_with_messages(session_id)
        transcript = ConversationTranscript(
            turns=[
                LLMMessageDict(
                    role=_role_for_llm(m.role), content=m.content
                )
                for m in chat_session.messages
            ]
        )
        return await BriefExtractor(self._llm).run(transcript)

    async def list_messages(self, session_id: UUID) -> list[Message]:
        await self._sessions.get(session_id)
        return await self._messages.list_for_session(session_id)

    async def list_sessions(self, project_id: UUID) -> list[Session]:
        await self._projects.get(project_id)
        return await self._sessions.list_for_project(project_id)

    async def _collect_asset_facts(self, project_id: UUID) -> list[AssetFacts]:
        """Pull the analysis stored on each asset and lift it into AssetFacts.

        Vision Analyzer hasn't landed yet - until it does, ``analysis``
        is empty for newly uploaded assets and we emit a minimal
        :class:`AssetFacts` carrying just the asset id. The Creative
        Director is fine with that: the prompt forbids fabrication, so
        an empty facts list just means "ask the user about the
        footage".
        """
        rows = await self._assets.list_for_project(project_id)
        facts: list[AssetFacts] = []
        for asset in rows:
            analysis = asset.analysis or {}
            try:
                facts.append(AssetFacts.model_validate({**analysis, "asset_id": asset.id}))
            except Exception:  # noqa: BLE001 - bad analysis JSON shouldn't break chat
                facts.append(AssetFacts(asset_id=asset.id, duration_seconds=0))
        return facts


def _role_for_llm(role: MessageRole) -> str:
    """Map persistent message roles onto the user/assistant the LLM expects."""
    if role is MessageRole.USER:
        return "user"
    return "assistant"
