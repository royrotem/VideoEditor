"""Agent orchestrator.

The orchestrator owns the multi-agent flow that turns a user brief plus
analysed assets into an approved :class:`EditDecisionList`. It does not
hold its own state - every step takes its inputs and produces its
outputs as Pydantic models, so the same orchestrator can drive a live
session or replay a recorded one.

This module ships the framework only. Concrete agent implementations
(Creative Director, Editing Planner, specialists, QA) plug in via the
registry in subsequent commits; this class is the seam they hang on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from app.agents.client import LLMClient
from app.agents.contracts import (
    AssetFacts,
    BriefPlan,
    EditDecisionList,
    QAReport,
)
from app.agents.registry import AgentRegistry
from app.core.errors import AppError
from app.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


_OutputT = TypeVar("_OutputT", bound=BaseModel)


class Orchestrator:
    """Coordinates the agent network for one editing session.

    The orchestrator exposes one public method per inter-agent step. The
    goal is for each method to be the *only* place that knows which
    agent name handles which step, so the rest of the codebase stays
    free of agent string literals.

    Stepwise design also keeps the orchestrator easy to test: any step
    can be exercised against a fake registry without touching the
    others.
    """

    AGENT_VISION_ANALYZER = "vision_analyzer"
    AGENT_EDITING_PLANNER = "editing_planner"
    AGENT_QA_REVIEWER = "qa_reviewer"

    def __init__(self, *, registry: AgentRegistry, llm: LLMClient) -> None:
        self._registry = registry
        self._llm = llm
        self._log = get_logger("agents.orchestrator")

    async def analyze_asset(self, asset_input: BaseModel) -> AssetFacts:
        """Run the Vision Analyzer over a single asset.

        ``asset_input`` is the Pydantic model the registered analyzer
        agent declares as its input (e.g.
        :class:`VisionAnalysisInput`). The orchestrator stays
        agent-input-agnostic on purpose — it does not know which
        fields the analyzer expects, only that it gets a Pydantic
        model.
        """
        return await self._run_agent(self.AGENT_VISION_ANALYZER, asset_input, AssetFacts)

    async def plan_edit(
        self,
        *,
        brief: BriefPlan,
        asset_facts: list[AssetFacts],
        previous_edl: EditDecisionList | None = None,
    ) -> EditDecisionList:
        """Ask the Planner to emit (or revise) an EDL for ``brief``."""
        from app.agents.editing_planner import PlannerInput

        payload = PlannerInput(brief=brief, asset_facts=asset_facts, previous_edl=previous_edl)
        return await self._run_agent(self.AGENT_EDITING_PLANNER, payload, EditDecisionList)

    async def review_edl(self, *, brief: BriefPlan, edl: EditDecisionList) -> QAReport:
        """Ask the QA Reviewer to compare ``edl`` against ``brief``."""
        from pydantic import BaseModel

        class _QAInput(BaseModel):
            brief: BriefPlan
            edl: EditDecisionList

        payload = _QAInput(brief=brief, edl=edl)
        return await self._run_agent(self.AGENT_QA_REVIEWER, payload, QAReport)

    # --- internals --------------------------------------------------

    async def _run_agent(
        self,
        agent_name: str,
        payload: BaseModel,
        expected_output: type[_OutputT],
    ) -> _OutputT:
        """Build an agent by name and run it; verify the output type."""
        from app.agents.base import Agent as _Agent  # local to avoid cycles

        agent = self._registry.build(agent_name, self._llm)
        if not isinstance(agent, _Agent):
            raise AppError(f"agent {agent_name!r} is not a single-shot Agent")
        result = await agent.run(payload)
        if not isinstance(result, expected_output):
            raise AppError(
                f"agent {agent_name!r} returned {type(result).__name__}, "
                f"expected {expected_output.__name__}"
            )
        self._log.info("orchestrator.step", agent=agent_name)
        return result
