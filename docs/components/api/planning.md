# Component: API / Planning

> Single endpoint that turns a :class:`BriefPlan` into an
> :class:`EditDecisionList` for a project. The bridge between chat
> output and the render pipeline.

## Purpose

Chat produces a :class:`BriefPlan` via
``POST /sessions/{id}/extract-brief``. The render endpoint consumes
an :class:`EditDecisionList`. This route fills the gap: take a brief
and the project's analysed asset facts, hand them to the Editing
Planner agent, return the EDL.

The frontend then ferries the EDL straight into
``POST /projects/{id}/render``. The frontend never has to construct
or mutate an EDL itself - that's an agent's job.

## Public interface

| Method | Path                              | Body            | Response              |
| ------ | --------------------------------- | --------------- | --------------------- |
| POST   | `/projects/{project_id}/plan-edit`| `PlanEditBody`  | `EditDecisionList` 200|

```python
class PlanEditBody(BaseModel):
    brief: BriefPlan
    previous_edl: EditDecisionList | None = None  # for revisions
```

## Inputs / outputs

- ``brief`` is the structured plan extracted from a chat. The
  endpoint does not mutate it - the Editing Planner agent reads it
  alongside the project's asset facts.
- ``previous_edl`` is optional. When present the planner amends it
  and emits a higher ``version`` (the same revision contract used by
  the render service for re-renders).
- The returned :class:`EditDecisionList` is the same Pydantic model
  the render endpoint already accepts.

## Errors

| Error                      | When                                         | HTTP |
| -------------------------- | -------------------------------------------- | ---- |
| `resource.not_found`       | Project id is unknown                        | 404  |
| `validation.failed`        | Project has no analysed assets               | 422  |
| `external.failed`          | Anthropic call failed or returned bad JSON   | 502  |

## Dependencies

- :class:`PlanningService` (`app.services.planning`).
- :class:`Orchestrator` from `app.agents.orchestrator`, which
  resolves the registered ``editing_planner`` agent.
- :class:`AssetRepository`, :class:`ProjectRepository`.

## How to test

- Service-level: ``backend/tests/test_planning_service.py`` covers
  happy path, unknown project, and the no-assets refusal.
- HTTP-level: ``backend/tests/test_routes_planning.py`` exercises
  the same paths through the FastAPI dependency overrides.

## Change log notes

- The endpoint **refuses** when the project has nothing to plan
  against (no analysed assets). This is intentional: a planner with
  empty asset facts will hallucinate or emit an empty timeline,
  neither of which we want shipped to the renderer.
- For revisions, pass the prior EDL via ``previous_edl``. The
  planner will return a new version with the requested change baked
  in.
