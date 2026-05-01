"""Unit tests for :class:`app.services.chat.ChatService`."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.agents.contracts import BriefPlan
from app.core.errors import NotFoundError, ValidationError
from app.db.enums import MessageRole, SessionStatus
from app.services.chat import ChatService

from tests.fakes import (
    FakeAssetRepository,
    FakeMessageRepository,
    FakeProjectRepository,
    FakeSessionRepository,
    ScriptedLLM,
)


@pytest.fixture
def projects() -> FakeProjectRepository:
    return FakeProjectRepository()


@pytest.fixture
def sessions_repo() -> FakeSessionRepository:
    return FakeSessionRepository()


@pytest.fixture
def messages_repo(sessions_repo: FakeSessionRepository) -> FakeMessageRepository:
    return FakeMessageRepository(sessions_repo)


def _build_service(
    *,
    projects: FakeProjectRepository,
    sessions_repo: FakeSessionRepository,
    messages_repo: FakeMessageRepository,
    llm: ScriptedLLM,
    assets: FakeAssetRepository | None = None,
) -> ChatService:
    return ChatService(
        llm=llm,
        projects=projects,
        assets=assets or FakeAssetRepository(),
        sessions=sessions_repo,
        messages=messages_repo,
    )


async def test_start_session_persists_opening_turn_and_director_reply(
    projects: FakeProjectRepository,
    sessions_repo: FakeSessionRepository,
    messages_repo: FakeMessageRepository,
) -> None:
    project = await projects.create(name="p", description=None)
    llm = ScriptedLLM(["יש לי שתי הצעות: A. ... B. ..."])
    service = _build_service(
        projects=projects,
        sessions_repo=sessions_repo,
        messages_repo=messages_repo,
        llm=llm,
    )

    chat, user_message, assistant_message = await service.start_session(
        project_id=project.id, brief="רוצה משהו קצר ואנרגטי"
    )

    assert chat.project_id == project.id
    assert chat.status is SessionStatus.ACTIVE
    assert "BRIEF:\nרוצה משהו קצר ואנרגטי" in user_message.content
    assert assistant_message.agent_name == "creative_director"
    assert assistant_message.role is MessageRole.AGENT
    assert "שתי הצעות" in assistant_message.content


async def test_start_session_rejects_empty_brief(
    projects: FakeProjectRepository,
    sessions_repo: FakeSessionRepository,
    messages_repo: FakeMessageRepository,
) -> None:
    service = _build_service(
        projects=projects,
        sessions_repo=sessions_repo,
        messages_repo=messages_repo,
        llm=ScriptedLLM([]),
    )
    with pytest.raises(ValidationError):
        await service.start_session(project_id=uuid4(), brief="   ")


async def test_start_session_rejects_unknown_project(
    projects: FakeProjectRepository,
    sessions_repo: FakeSessionRepository,
    messages_repo: FakeMessageRepository,
) -> None:
    service = _build_service(
        projects=projects,
        sessions_repo=sessions_repo,
        messages_repo=messages_repo,
        llm=ScriptedLLM(["x"]),
    )
    with pytest.raises(NotFoundError):
        await service.start_session(project_id=uuid4(), brief="x")


async def test_send_turn_appends_messages_and_does_not_close_when_not_converged(
    projects: FakeProjectRepository,
    sessions_repo: FakeSessionRepository,
    messages_repo: FakeMessageRepository,
) -> None:
    project = await projects.create(name="p", description=None)
    llm = ScriptedLLM(["שאלה ראשונה...", "מה דעתך על מוזיקה?"])
    service = _build_service(
        projects=projects,
        sessions_repo=sessions_repo,
        messages_repo=messages_repo,
        llm=llm,
    )
    chat, _, _ = await service.start_session(
        project_id=project.id, brief="רעיון"
    )

    user_msg, assistant_msg, converged = await service.send_turn(
        session_id=chat.id, content="אני אוהב פופ"
    )

    assert user_msg.content == "אני אוהב פופ"
    assert assistant_msg.content == "מה דעתך על מוזיקה?"
    assert converged is False
    refreshed = await sessions_repo.get(chat.id)
    assert refreshed.status is SessionStatus.ACTIVE


async def test_send_turn_closes_session_when_director_emits_summary(
    projects: FakeProjectRepository,
    sessions_repo: FakeSessionRepository,
    messages_repo: FakeMessageRepository,
) -> None:
    project = await projects.create(name="p", description=None)
    llm = ScriptedLLM(
        [
            "יש לי הצעה: סרטון אנרגטי של 30 שניות.",
            "סיכום: סרטון אנרגטי של 30 שניות עם פופ עברי.",
        ]
    )
    service = _build_service(
        projects=projects,
        sessions_repo=sessions_repo,
        messages_repo=messages_repo,
        llm=llm,
    )
    chat, _, _ = await service.start_session(
        project_id=project.id, brief="רעיון"
    )

    _, _, converged = await service.send_turn(
        session_id=chat.id, content="כן, בוא נלך עם זה"
    )

    assert converged is True
    refreshed = await sessions_repo.get(chat.id)
    assert refreshed.status is SessionStatus.CLOSED


async def test_send_turn_rejects_closed_session(
    projects: FakeProjectRepository,
    sessions_repo: FakeSessionRepository,
    messages_repo: FakeMessageRepository,
) -> None:
    project = await projects.create(name="p", description=None)
    llm = ScriptedLLM(["x"])
    service = _build_service(
        projects=projects,
        sessions_repo=sessions_repo,
        messages_repo=messages_repo,
        llm=llm,
    )
    chat, _, _ = await service.start_session(
        project_id=project.id, brief="x"
    )
    await sessions_repo.close(chat.id)

    with pytest.raises(ValidationError, match="closed"):
        await service.send_turn(session_id=chat.id, content="היי")


async def test_extract_brief_runs_brief_extractor_on_full_transcript(
    projects: FakeProjectRepository,
    sessions_repo: FakeSessionRepository,
    messages_repo: FakeMessageRepository,
) -> None:
    project = await projects.create(name="p", description=None)
    director_reply = "סיכום: סרטון של 30 שניות, אנרגטי, עם פופ עברי."
    extractor_reply = json.dumps(
        {
            "title": "חתונה — קאט קצר",
            "intent": "סיכום אנרגטי של 30 שניות",
            "target_duration_seconds": 30,
            "style_notes": ["אנרגטי"],
            "music_direction": "פופ עברי",
            "pacing": "fast",
        }
    )
    llm = ScriptedLLM([director_reply, extractor_reply])
    service = _build_service(
        projects=projects,
        sessions_repo=sessions_repo,
        messages_repo=messages_repo,
        llm=llm,
    )
    chat, _, _ = await service.start_session(
        project_id=project.id, brief="רעיון"
    )

    plan = await service.extract_brief(session_id=chat.id)

    assert isinstance(plan, BriefPlan)
    assert plan.title == "חתונה — קאט קצר"
    assert plan.target_duration_seconds == 30
