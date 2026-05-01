"""Unit tests for :class:`app.services.planning.PlanningService`."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from app.agents.contracts import BriefPlan, EditDecisionList
from app.agents.registry import AgentRegistry
from app.core.errors import NotFoundError, ValidationError
from app.db.enums import AssetStatus
from app.services.planning import PlanningService

from tests.fakes import FakeAssetRepository, FakeProjectRepository, ScriptedLLM


def _planner_reply(asset_id: UUID, *, version: int = 1) -> str:
    return json.dumps(
        {
            "version": version,
            "timeline": [
                {
                    "kind": "video",
                    "clips": [
                        {
                            "clip": {
                                "asset_id": str(asset_id),
                                "source_start_seconds": 0,
                                "source_end_seconds": 4,
                            },
                            "timeline_start_seconds": 0,
                            "transition_in": "fade",
                            "transition_out": "cut",
                        }
                    ],
                }
            ],
            "audio": {
                "music_url": None,
                "voice_over_asset_id": None,
                "duck_music_under_voice": True,
                "target_lufs": -14.0,
            },
            "subtitles": None,
            "color": None,
            "output": {
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "container": "mp4",
            },
        }
    )


def _registry_with_real_planner() -> AgentRegistry:
    """A registry containing every agent the planning step might touch.

    Importing ``app.agents`` populates the global registry; we reuse it
    rather than mocking the planner so the test exercises the real
    JSON-parsing behaviour.
    """
    import app.agents  # noqa: F401 - triggers registration
    from app.agents.registry import get_registry

    return get_registry()


@pytest.fixture
def brief() -> BriefPlan:
    return BriefPlan(
        title="חתונה — קאט קצר",
        intent="סיכום אנרגטי של 30 שניות",
        target_duration_seconds=30,
        pacing="fast",
    )


async def test_plan_calls_editing_planner_against_project_assets(
    brief: BriefPlan,
) -> None:
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    project = await projects.create(name="p", description=None)
    asset = await assets.create(
        project_id=project.id,
        filename="clip.mp4",
        content_type="video/mp4",
        size_bytes=1024,
        s3_bucket="b",
        s3_key="k",
        status=AssetStatus.READY,
        analysis={"duration_seconds": 30.0},
    )
    llm = ScriptedLLM([_planner_reply(asset.id)])

    service = PlanningService(
        llm=llm,
        projects=projects,
        assets=assets,
        registry=_registry_with_real_planner(),
    )

    edl = await service.plan(project_id=project.id, brief=brief)

    assert isinstance(edl, EditDecisionList)
    assert edl.version == 1
    assert len(edl.timeline) == 1
    # Planner saw the brief + asset facts in its user message.
    assert llm.calls
    body = llm.calls[0]["messages"][0].content  # type: ignore[index]
    assert "חתונה" in body
    assert str(asset.id) in body


async def test_plan_rejects_unknown_project(brief: BriefPlan) -> None:
    service = PlanningService(
        llm=ScriptedLLM([]),
        projects=FakeProjectRepository(),
        assets=FakeAssetRepository(),
        registry=_registry_with_real_planner(),
    )

    with pytest.raises(NotFoundError):
        await service.plan(project_id=uuid4(), brief=brief)


async def test_plan_refuses_when_project_has_no_assets(brief: BriefPlan) -> None:
    projects = FakeProjectRepository()
    project = await projects.create(name="p", description=None)
    service = PlanningService(
        llm=ScriptedLLM([]),
        projects=projects,
        assets=FakeAssetRepository(),
        registry=_registry_with_real_planner(),
    )

    with pytest.raises(ValidationError, match="no analysed assets"):
        await service.plan(project_id=project.id, brief=brief)
