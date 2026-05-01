# Component: Pipeline / EDL Validator

> Structural validation of an :class:`EditDecisionList` against the
> assets that actually exist for a project. The first stage of the
> render pipeline; also consumed by the planner-feedback loop.

## Purpose

The Editing Planner is an LLM and will sometimes emit EDLs that look
plausible but reference an asset that does not exist, point at
timestamps past the end of a clip, or regress the version number.
Rendering against a bad EDL wastes time and produces broken output.

The validator catches the failures the LLM is most likely to make.
Errors block rendering. Warnings allow rendering but should be shown
to the user. The validator is a pure function over plain Pydantic /
dataclass values - no DB session, no LLM calls - so it is trivially
unit-tested and replayable.

## Public interface

```python
class ValidationSeverity(StrEnum):
    ERROR    # blocks rendering
    WARNING  # allow rendering, surface in UI

class ValidationIssue(BaseModel):
    severity: ValidationSeverity
    code: str         # stable id, e.g. "asset_not_found"
    message: str
    location: str | None  # "timeline[0].clips[2]"

class ValidationReport(BaseModel):
    ok: bool          # true iff no errors
    issues: list[ValidationIssue]

@dataclass(slots=True, frozen=True)
class AssetSpec:
    asset_id: UUID
    duration_seconds: float

    @classmethod
    def from_asset_row(cls, asset) -> "AssetSpec": ...

class EdlValidator:
    def __init__(self, assets: Iterable[AssetSpec]) -> None: ...
    def validate(self, edl: EditDecisionList, *, previous_version: int | None = None) -> ValidationReport: ...
```

## Rules

| Code                              | Meaning                                                         | Severity |
| --------------------------------- | --------------------------------------------------------------- | -------- |
| `asset_not_found`                 | A clip references an asset id that is not in the project        | error    |
| `source_range_inverted`           | `source_end_seconds <= source_start_seconds`                    | error    |
| `source_start_negative`           | `source_start_seconds < 0`                                      | error    |
| `source_end_past_asset_duration`  | `source_end_seconds > asset.duration_seconds`                   | error    |
| `timeline_clip_out_of_order`      | `timeline_start_seconds` decreases inside a track               | error    |
| `version_not_monotonic`           | `edl.version <= previous_version`                               | error    |

The list is intentionally short. Per-pixel concerns (codec support,
fps mismatch, audio sample rate) belong to the render stage that
follows; they are caught by FFmpeg, not by this validator.

## Inputs

- ``assets``: iterable of :class:`AssetSpec`. Build via
  :meth:`AssetSpec.from_asset_row` from the project's asset rows -
  ``duration_seconds`` is read from the asset's ``analysis`` JSON
  (populated by the Vision Analyzer).
- ``edl``: the :class:`EditDecisionList` produced by the Editing
  Planner.
- ``previous_version``: optional. When supplied, the validator
  enforces strict monotonicity on revisions.

## Outputs

A :class:`ValidationReport`. The validator never raises - callers
inspect ``report.ok`` and ``report.issues``.

## Dependencies

- Pydantic models from :mod:`app.agents.contracts`.
- Nothing else. No DB, no external services.

## Errors

The validator never raises. Use ``report.ok`` to decide whether to
proceed.

## How to test

``backend/tests/test_edl_validator.py`` covers each rule and the ORM
bridge.

## Change log notes

- "Asset has no duration yet" (Vision Analyzer hasn't run) shows up
  as ``source_end_past_asset_duration`` because ``duration_seconds``
  defaults to 0. This is intentional: the validator's job is to
  refuse to render against unknown footage.
- New rules go here, not into the render stage. Keep render free of
  EDL-shape checks - they are slow to debug and easy to test cleanly
  here.
