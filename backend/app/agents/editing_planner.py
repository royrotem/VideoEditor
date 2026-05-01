"""Editing Planner - turn a BriefPlan + AssetFacts into an EditDecisionList.

This is the single most important agent in the network: its output is
what the deterministic render pipeline consumes. We constrain it
hard - same JSON-only contract every other agent uses, plus a system
prompt that forbids referencing assets that don't exist.

Revision is supported: passing the previous EDL in lets the model
amend it (keeping ``version`` monotonic) instead of starting from
scratch. The post-render "ask for changes in words" feature in the
roadmap relies on this.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.agents.contracts import AssetFacts, BriefPlan, EditDecisionList
from app.agents.prompts.editing_planner import EDITING_PLANNER_SYSTEM_PROMPT
from app.agents.registry import get_registry


class PlannerInput(BaseModel):
    """Everything the Editing Planner needs to produce an EDL.

    Carries ``previous_edl`` so the agent can revise rather than rewrite.
    The orchestrator builds this on the way in; tests can build it
    directly.
    """

    brief: BriefPlan
    asset_facts: list[AssetFacts] = Field(default_factory=list)
    previous_edl: EditDecisionList | None = None


@get_registry().register
class EditingPlanner(Agent[PlannerInput, EditDecisionList]):
    """Single-shot agent that emits an :class:`EditDecisionList`."""

    name = "editing_planner"
    model = "claude-sonnet-4-6"
    system_prompt = EDITING_PLANNER_SYSTEM_PROMPT
    output_model = EditDecisionList
