# Component: Agents / Editing Planner

> Single-shot agent that produces an :class:`EditDecisionList` from an
> approved :class:`BriefPlan` plus the analysed :class:`AssetFacts`.
> Its output is what the deterministic render pipeline executes.

## Purpose

Separate creative reasoning from deterministic media work. The Brief
Extractor distilled the user's intent into a :class:`BriefPlan`; the
Vision Analyzer tagged each asset; the Editing Planner is the only
agent allowed to invent timing, transitions, and clip selection.
Everything downstream (Cut Specialist, Audio Engineer, QA Reviewer,
the FFmpeg pipeline) consumes its EDL.

The planner also handles **revisions**: passing the prior EDL via
``previous_edl`` lets it amend the existing plan and emit a higher
``version``, which keeps the editing history append-only and the
"ask for changes in words" flow trivial to implement.

## Public interface

```python
class PlannerInput(BaseModel):
    brief: BriefPlan
    asset_facts: list[AssetFacts]
    previous_edl: EditDecisionList | None = None

class EditingPlanner(Agent[PlannerInput, EditDecisionList]):
    name = "editing_planner"
    model = "claude-sonnet-4-6"
    output_model = EditDecisionList
```

The orchestrator's :meth:`Orchestrator.plan_edit` is the recommended
entry point - it builds a :class:`PlannerInput` and routes through the
registry.

## Inputs

A :class:`PlannerInput`:

- ``brief`` - the approved :class:`BriefPlan` (title, intent, target
  duration, pacing, optional music direction).
- ``asset_facts`` - one :class:`AssetFacts` per uploaded asset. The
  prompt forbids referencing assets that aren't here.
- ``previous_edl`` - optional. When present, the planner amends it
  and emits ``version = previous_edl.version + 1``.

## Outputs

An :class:`app.agents.contracts.EditDecisionList`. The base
:class:`Agent` validates the model's JSON reply against the schema -
schema mismatches surface as :class:`ExternalServiceError`.

## Constraints encoded in the system prompt

- Every ``ClipReference`` must reference an asset that appears in
  ``asset_facts``, with timestamps inside that asset's
  ``duration_seconds``.
- The total timeline duration must be within ±10% of
  ``brief.target_duration_seconds``.
- Pacing maps to clip lengths (fast → 1-3s, medium → 3-6s,
  slow → 6-12s).
- ``transition_in`` defaults to ``"fade"`` for the very first clip and
  ``transition_out`` to ``"fade"`` for the last; ``"dissolve"`` between
  scenes that need a soft cut; ``"cut"`` everywhere else.
- ``output`` defaults to 1920×1080 / 30fps / mp4 unless the brief
  hints at a vertical format ("stories", "TikTok").

## Dependencies

- :class:`app.agents.base.Agent` (JSON parsing + Pydantic validation).
- :data:`app.agents.prompts.editing_planner.EDITING_PLANNER_SYSTEM_PROMPT`.

## Errors

| Error                  | When                                                 |
| ---------------------- | ---------------------------------------------------- |
| `ExternalServiceError` | Non-JSON reply, schema mismatch, or referenced asset id absent (latter caught by validation when the resolver pass runs) |

## How to test

- Unit: ``backend/tests/test_editing_planner.py`` covers happy path,
  model selection, revision (carries ``previous_edl``), and registry
  registration.
- Integration: a future smoke test will run the planner against the
  real model with a small fixture session.

## Change log notes

- Sonnet 4.6 (not Opus) because this is a constrained, schema-bound
  task with no open-ended reasoning. Re-evaluate the model choice
  only if the planner starts emitting EDLs that consistently violate
  asset-id or duration constraints - those are quality-of-output
  signals, not correctness signals.
- Future agents (Cut Specialist, Audio Engineer, Color/Effects) will
  refine an existing EDL by reading ``previous_edl`` and emitting a
  new version - the same revision contract used here.
