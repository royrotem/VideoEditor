"""Edit-planning use case.

Bridges the chat layer (which produces a :class:`BriefPlan`) and the
render pipeline (which consumes an :class:`EditDecisionList`). Pulls
the project's analysed asset facts from the database, asks the
:class:`Orchestrator` to plan an EDL, and returns it.

Lives in ``services`` rather than in ``agents`` because it is the
orchestration layer - it owns the database access and assembles the
inputs the agent expects.
"""

from __future__ import annotations

from uuid import UUID

from app.agents.client import LLMClient
from app.agents.contracts import AssetFacts, BriefPlan, EditDecisionList
from app.agents.orchestrator import Orchestrator
from app.agents.registry import AgentRegistry, get_registry
from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.db.models import Asset
from app.repositories.assets import AssetRepository
from app.repositories.projects import ProjectRepository


class PlanningService:
    """Plan an :class:`EditDecisionList` for a project + brief."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        projects: ProjectRepository,
        assets: AssetRepository,
        registry: AgentRegistry | None = None,
    ) -> None:
        self._llm = llm
        self._projects = projects
        self._assets = assets
        self._registry = registry or get_registry()
        self._log = get_logger("services.planning")

    async def plan(
        self,
        *,
        project_id: UUID,
        brief: BriefPlan,
        previous_edl: EditDecisionList | None = None,
    ) -> EditDecisionList:
        """Run the Editing Planner over the project's asset facts.

        The project is fetched first so an unknown id surfaces as a
        404 before the (much slower) LLM call. We refuse to plan
        when the project has no analysed assets - the planner has
        nothing to build a timeline from.
        """
        await self._projects.get(project_id)

        asset_rows = await self._assets.list_for_project(project_id)
        asset_facts = [_to_asset_facts(asset) for asset in asset_rows]
        if not asset_facts:
            raise ValidationError(
                "project has no analysed assets to plan against"
            )

        orchestrator = Orchestrator(registry=self._registry, llm=self._llm)
        edl = await orchestrator.plan_edit(
            brief=brief,
            asset_facts=asset_facts,
            previous_edl=previous_edl,
        )
        self._log.info(
            "planning.complete",
            project_id=str(project_id),
            asset_count=len(asset_facts),
            edl_version=edl.version,
        )
        return edl


def _to_asset_facts(asset: Asset) -> AssetFacts:
    """Lift a DB row + its analysis JSON into an :class:`AssetFacts`.

    Falls back to a duration of zero when the asset has not been
    analysed yet - the EDL Validator will catch that downstream
    rather than letting us produce a bogus plan.
    """
    analysis = asset.analysis or {}
    return AssetFacts.model_validate({**analysis, "asset_id": asset.id})
