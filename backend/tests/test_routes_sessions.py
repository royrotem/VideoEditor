"""HTTP-level tests for chat session routes."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_asset_repository,
    get_llm_client,
    get_message_repository,
    get_object_store,
    get_project_repository,
    get_session_repository,
)
from app.core.config import Settings
from app.main import create_app

from tests.fakes import (
    FakeAssetRepository,
    FakeMessageRepository,
    FakeProjectRepository,
    FakeSessionRepository,
    InMemoryObjectStore,
    ScriptedLLM,
)


@pytest.fixture
def llm_replies() -> list[str]:
    """Per-test list the test client mutates to queue model replies."""
    return []


@pytest.fixture
def fakes() -> tuple[
    FakeProjectRepository,
    FakeAssetRepository,
    FakeSessionRepository,
    FakeMessageRepository,
    InMemoryObjectStore,
]:
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    sessions_repo = FakeSessionRepository()
    messages_repo = FakeMessageRepository(sessions_repo)
    store = InMemoryObjectStore()
    return projects, assets, sessions_repo, messages_repo, store


@pytest.fixture
def app_client(
    fakes: tuple[
        FakeProjectRepository,
        FakeAssetRepository,
        FakeSessionRepository,
        FakeMessageRepository,
        InMemoryObjectStore,
    ],
    llm_replies: list[str],
) -> Iterator[TestClient]:
    projects, assets, sessions_repo, messages_repo, store = fakes
    app = create_app(settings=Settings(environment="test"))

    llm = ScriptedLLM(llm_replies)

    app.dependency_overrides[get_project_repository] = lambda: projects
    app.dependency_overrides[get_asset_repository] = lambda: assets
    app.dependency_overrides[get_session_repository] = lambda: sessions_repo
    app.dependency_overrides[get_message_repository] = lambda: messages_repo
    app.dependency_overrides[get_object_store] = lambda: store
    app.dependency_overrides[get_llm_client] = lambda: llm

    with TestClient(app) as client:
        yield client


def _create_project(client: TestClient) -> str:
    return client.post(
        "/projects", json={"name": "p", "description": None}
    ).json()["id"]


def test_start_session_returns_director_reply(
    app_client: TestClient, llm_replies: list[str]
) -> None:
    llm_replies.append("יש לי שתי הצעות: A. אנרגטי. B. שקט.")
    project_id = _create_project(app_client)

    response = app_client.post(
        f"/projects/{project_id}/sessions",
        json={"brief": "סרטון מהחתונה של אחותי"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["session"]["status"] == "active"
    assert "BRIEF:\nסרטון מהחתונה של אחותי" in body["user_message"]["content"]
    assert "שתי הצעות" in body["assistant_message"]["content"]
    assert body["assistant_message"]["agent_name"] == "creative_director"


def test_send_turn_marks_converged_when_director_summarises(
    app_client: TestClient, llm_replies: list[str]
) -> None:
    llm_replies.extend(
        [
            "מה דעתך על מוזיקה?",
            "סיכום: סרטון אנרגטי של 30 שניות עם פופ עברי.",
        ]
    )
    project_id = _create_project(app_client)
    session_id = app_client.post(
        f"/projects/{project_id}/sessions",
        json={"brief": "רעיון"},
    ).json()["session"]["id"]

    response = app_client.post(
        f"/sessions/{session_id}/messages", json={"content": "פופ עברי"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["converged"] is True
    assert body["assistant_message"]["content"].startswith("סיכום:")


def test_list_messages_returns_chat_history_in_order(
    app_client: TestClient, llm_replies: list[str]
) -> None:
    llm_replies.extend(["שלום!", "ועוד רעיון..."])
    project_id = _create_project(app_client)
    session_id = app_client.post(
        f"/projects/{project_id}/sessions", json={"brief": "x"}
    ).json()["session"]["id"]
    app_client.post(f"/sessions/{session_id}/messages", json={"content": "תודה"})

    response = app_client.get(f"/sessions/{session_id}/messages")

    assert response.status_code == 200
    history = response.json()
    assert [m["role"] for m in history] == ["user", "agent", "user", "agent"]
    assert history[1]["content"] == "שלום!"


def test_extract_brief_returns_structured_brief_plan(
    app_client: TestClient, llm_replies: list[str]
) -> None:
    llm_replies.extend(
        [
            "סיכום: סרטון של 30 שניות, אנרגטי, עם פופ עברי.",
            json.dumps(
                {
                    "title": "חתונה — קאט קצר",
                    "intent": "סיכום אנרגטי של 30 שניות",
                    "target_duration_seconds": 30,
                    "style_notes": ["אנרגטי"],
                    "music_direction": "פופ עברי",
                    "pacing": "fast",
                }
            ),
        ]
    )
    project_id = _create_project(app_client)
    session_id = app_client.post(
        f"/projects/{project_id}/sessions", json={"brief": "x"}
    ).json()["session"]["id"]

    response = app_client.post(f"/sessions/{session_id}/extract-brief")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "חתונה — קאט קצר"
    assert body["pacing"] == "fast"


def test_start_session_rejects_unknown_project(
    app_client: TestClient, llm_replies: list[str]
) -> None:
    llm_replies.append("x")
    response = app_client.post(
        "/projects/00000000-0000-0000-0000-000000000000/sessions",
        json={"brief": "x"},
    )
    assert response.status_code == 404
