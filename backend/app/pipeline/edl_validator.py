"""Structural validation of an :class:`EditDecisionList`.

Runs before any render and (eventually) right after the Editing
Planner emits a new EDL. Catches the failure modes the LLM is most
likely to introduce:

- references to assets that don't exist for the project,
- source timestamps that fall outside an asset's actual duration,
- inverted time ranges (``source_end <= source_start``),
- timeline gaps where ``timeline_start_seconds`` is decreasing within a
  track,
- version regressions vs. the previous stored EDL.

The validator never raises on these - it returns a structured
:class:`ValidationReport`. Callers decide whether to ask the planner to
revise (warnings) or refuse to render (errors).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.contracts import EditDecisionList, TimelineClip


class ValidationSeverity(StrEnum):
    """How serious a validation issue is.

    Errors block rendering; warnings allow rendering but should be
    surfaced in the UI so the user can decide.
    """

    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    """One problem found in an EDL."""

    severity: ValidationSeverity
    code: str = Field(description="Stable machine identifier, e.g. asset_not_found")
    message: str
    location: str | None = Field(
        default=None,
        description="Pointer into the EDL (track index, clip index, ...)",
    )


class ValidationReport(BaseModel):
    """Result of validating an EDL.

    ``ok`` is true iff there are no errors. Warnings do not flip it.
    """

    ok: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


@dataclass(slots=True, frozen=True)
class AssetSpec:
    """The minimum set of facts the validator needs about an asset.

    Lifting this out of the ORM keeps the validator a pure function
    over plain data - easy to unit-test, no DB session required.
    """

    asset_id: UUID
    duration_seconds: float

    @classmethod
    def from_asset_row(cls, asset: object) -> AssetSpec:
        """Build an :class:`AssetSpec` from a DB row (or any duck-type).

        Reads ``duration_seconds`` from ``asset.analysis`` (the JSON
        blob populated by the Vision Analyzer). Falls back to 0 when
        the asset has not been analysed yet - in which case every EDL
        that references it will fail with
        ``source_end_past_asset_duration`` until analysis runs, which
        is the correct behaviour: we will not render against a clip we
        haven't measured.
        """
        analysis = getattr(asset, "analysis", None) or {}
        duration = float(analysis.get("duration_seconds", 0.0))
        return cls(asset_id=asset.id, duration_seconds=duration)  # type: ignore[attr-defined]


class EdlValidator:
    """Validates an EDL against the assets that exist for a project.

    The constructor takes an iterable of :class:`AssetSpec` (typically
    built by the caller from the ``assets`` table for the project).
    Stateless after construction - one validator instance can validate
    multiple EDLs against the same asset set.
    """

    def __init__(self, assets: Iterable[AssetSpec]) -> None:
        self._assets: dict[UUID, AssetSpec] = {a.asset_id: a for a in assets}

    def validate(
        self,
        edl: EditDecisionList,
        *,
        previous_version: int | None = None,
    ) -> ValidationReport:
        """Run every check; return a report. Never raises."""
        issues: list[ValidationIssue] = []

        issues.extend(self._check_version(edl, previous_version))
        issues.extend(self._check_timeline(edl))

        ok = not any(i.severity is ValidationSeverity.ERROR for i in issues)
        return ValidationReport(ok=ok, issues=issues)

    def _check_version(
        self, edl: EditDecisionList, previous_version: int | None
    ) -> list[ValidationIssue]:
        if previous_version is None:
            return []
        if edl.version <= previous_version:
            return [
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="version_not_monotonic",
                    message=(
                        f"EDL version {edl.version} is not greater than "
                        f"previous version {previous_version}"
                    ),
                    location="version",
                )
            ]
        return []

    def _check_timeline(self, edl: EditDecisionList) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for track_idx, track in enumerate(edl.timeline):
            previous_start: float = -1.0
            for clip_idx, clip in enumerate(track.clips):
                where = f"timeline[{track_idx}].clips[{clip_idx}]"
                issues.extend(self._check_clip(clip, where))

                if clip.timeline_start_seconds < previous_start:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="timeline_clip_out_of_order",
                            message=(
                                f"clip starts at {clip.timeline_start_seconds:.2f}s, "
                                f"earlier than the preceding clip at {previous_start:.2f}s"
                            ),
                            location=where,
                        )
                    )
                previous_start = clip.timeline_start_seconds
        return issues

    def _check_clip(self, clip: TimelineClip, where: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        ref = clip.clip
        asset = self._assets.get(ref.asset_id)

        if asset is None:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="asset_not_found",
                    message=f"clip references unknown asset {ref.asset_id}",
                    location=where,
                )
            )
            # No further per-clip checks if the asset is missing.
            return issues

        if ref.source_end_seconds <= ref.source_start_seconds:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="source_range_inverted",
                    message=(
                        f"source_end_seconds ({ref.source_end_seconds}) must be "
                        f"strictly greater than source_start_seconds "
                        f"({ref.source_start_seconds})"
                    ),
                    location=where,
                )
            )

        if ref.source_start_seconds < 0:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="source_start_negative",
                    message=(f"source_start_seconds is negative: " f"{ref.source_start_seconds}"),
                    location=where,
                )
            )

        if ref.source_end_seconds > asset.duration_seconds:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="source_end_past_asset_duration",
                    message=(
                        f"source_end_seconds {ref.source_end_seconds:.2f}s is past "
                        f"asset duration {asset.duration_seconds:.2f}s"
                    ),
                    location=where,
                )
            )

        return issues
