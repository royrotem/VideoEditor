"""Unit tests for :class:`app.agents.orchestrator.Orchestrator`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agents.base import Agent
from app.agents.client import LLMClient, LLMMessage, LLMResponse
from app.agents.contracts import (
    AssetFacts,
    BriefPlan,
    EditDecisionList,
    OutputSpec,
    QAReport,
    Track,
)
from app.agents.orchestrator import Orchestrator
from app.agents.registry import AgentRegistry
from app.core.errors import AppError, NotFoundError


class _StubLLM(LLMClient):
    """Returns whatever string was queued; not used directly here."""

    async def complete(  # type: ignore[override]
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 16000,
        cache_system_prompt: bool = True,
    ) -> LLMResponse:
        return LLMResponse(text="{}")


# Stub agents with deterministic outputs so we can verify routing only.


class _StubVision(Agent):  # type: ignore[type-arg]
    name = "vision_analyzer"
    model = "claude-sonnet-4-6"
    system_prompt = "stub"
    output_model = AssetFacts

    async def run(self, _: object) -> AssetFacts:  # type: ignore[override]
        return AssetFacts(asset_id=uuid4(), duration_seconds=12.5)


class _StubPlanner(Agent):  # type: ignore[type-arg]
    name = "editing_planner"
    model = "claude-sonnet-4-6"
    system_prompt = "stub"
    output_model = EditDecisionList

    async def run(self, _: object) -> EditDecisionList:  # type: ignore[override]
        return EditDecisionList(
            version=1, timeline=[Track(kind="video", clips=[])], output=OutputSpec()
        )


class _StubQA(Agent):  # type: ignore[type-arg]
    name = "qa_reviewer"
    model = "claude-sonnet-4-6"
    system_prompt = "stub"
    output_model = QAReport

    async def run(self, _: object) -> QAReport:  # type: ignore[override]
        return QAReport(approved=True, summary="ok")


@pytest.fixture
def orchestrator() -> Orchestrator:
    registry = AgentRegistry()
    registry.register(_StubVision)
    registry.register(_StubPlanner)
    registry.register(_StubQA)
    return Orchestrator(registry=registry, llm=_StubLLM())


async def test_analyze_asset_routes_to_vision_analyzer(
    orchestrator: Orchestrator,
) -> None:
    facts = await orchestrator.analyze_asset({"asset_id": str(uuid4())})

    assert isinstance(facts, AssetFacts)
    assert facts.duration_seconds == 12.5


async def test_plan_edit_returns_versioned_edl(orchestrator: Orchestrator) -> None:
    brief = BriefPlan(title="ערב חתונה", intent="סיכום קצר ומרגש", target_duration_seconds=60)

    edl = await orchestrator.plan_edit(brief=brief, asset_facts=[])

    assert edl.version == 1
    assert len(edl.timeline) == 1


async def test_review_edl_returns_qa_report(orchestrator: Orchestrator) -> None:
    brief = BriefPlan(title="t", intent="i", target_duration_seconds=60)
    edl = EditDecisionList(version=1, timeline=[Track(clips=[])])

    report = await orchestrator.review_edl(brief=brief, edl=edl)

    assert report.approved is True


async def test_unknown_agent_raises() -> None:
    orchestrator = Orchestrator(registry=AgentRegistry(), llm=_StubLLM())

    with pytest.raises(NotFoundError):
        await orchestrator.analyze_asset({"asset_id": str(uuid4())})


async def test_orchestrator_rejects_chat_agent_for_single_shot_step() -> None:
    from app.agents.base import ChatAgent

    class _ChatStub(ChatAgent):
        name = "vision_analyzer"  # collide with the single-shot slot
        model = "claude-opus-4-7"
        system_prompt = "stub"

    registry = AgentRegistry()
    registry.register(_ChatStub)
    orchestrator = Orchestrator(registry=registry, llm=_StubLLM())

    with pytest.raises(AppError, match="not a single-shot Agent"):
        await orchestrator.analyze_asset({"asset_id": str(uuid4())})
