"""Unit tests for :class:`app.pipeline.edl_validator.EdlValidator`."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.agents.contracts import (
    AudioPlan,
    ClipReference,
    EditDecisionList,
    OutputSpec,
    TimelineClip,
    Track,
)
from app.pipeline.edl_validator import (
    AssetSpec,
    EdlValidator,
    ValidationSeverity,
)


def _clip(
    *,
    asset_id: UUID,
    source_start: float,
    source_end: float,
    timeline_start: float = 0.0,
) -> TimelineClip:
    return TimelineClip(
        clip=ClipReference(
            asset_id=asset_id,
            source_start_seconds=source_start,
            source_end_seconds=source_end,
        ),
        timeline_start_seconds=timeline_start,
    )


def _edl(*clips: TimelineClip, version: int = 1) -> EditDecisionList:
    return EditDecisionList(
        version=version,
        timeline=[Track(kind="video", clips=list(clips))],
        audio=AudioPlan(),
        output=OutputSpec(),
    )


# --- happy path ----------------------------------------------------------


def test_valid_edl_returns_ok_report() -> None:
    asset_id = uuid4()
    validator = EdlValidator([AssetSpec(asset_id=asset_id, duration_seconds=30.0)])

    report = validator.validate(
        _edl(_clip(asset_id=asset_id, source_start=0, source_end=10))
    )

    assert report.ok is True
    assert report.issues == []


# --- per-clip checks -----------------------------------------------------


def test_unknown_asset_id_yields_error() -> None:
    validator = EdlValidator([AssetSpec(asset_id=uuid4(), duration_seconds=30.0)])

    report = validator.validate(
        _edl(_clip(asset_id=uuid4(), source_start=0, source_end=5))
    )

    assert report.ok is False
    codes = [issue.code for issue in report.issues]
    assert codes == ["asset_not_found"]


def test_source_end_past_asset_duration_is_error() -> None:
    asset_id = uuid4()
    validator = EdlValidator([AssetSpec(asset_id=asset_id, duration_seconds=10.0)])

    report = validator.validate(
        _edl(_clip(asset_id=asset_id, source_start=0, source_end=20))
    )

    assert report.ok is False
    assert any(i.code == "source_end_past_asset_duration" for i in report.issues)


def test_source_range_inverted_is_error() -> None:
    asset_id = uuid4()
    validator = EdlValidator([AssetSpec(asset_id=asset_id, duration_seconds=30.0)])

    # Pydantic itself rejects source_end_seconds <= 0, but we want to
    # exercise inverted-but-positive (e.g. start=5, end=3).
    edl = EditDecisionList(
        version=1,
        timeline=[
            Track(
                kind="video",
                clips=[
                    TimelineClip(
                        clip=ClipReference(
                            asset_id=asset_id,
                            source_start_seconds=5,
                            source_end_seconds=3,
                        ),
                        timeline_start_seconds=0,
                    )
                ],
            )
        ],
    )

    report = validator.validate(edl)
    assert any(i.code == "source_range_inverted" for i in report.issues)


# --- timeline-level checks -----------------------------------------------


def test_clips_out_of_order_within_track_is_error() -> None:
    asset_id = uuid4()
    validator = EdlValidator([AssetSpec(asset_id=asset_id, duration_seconds=30.0)])

    report = validator.validate(
        _edl(
            _clip(asset_id=asset_id, source_start=0, source_end=5, timeline_start=10),
            _clip(asset_id=asset_id, source_start=5, source_end=8, timeline_start=2),
        )
    )

    assert report.ok is False
    assert any(i.code == "timeline_clip_out_of_order" for i in report.issues)


# --- version checks ------------------------------------------------------


def test_non_monotonic_version_is_error() -> None:
    asset_id = uuid4()
    validator = EdlValidator([AssetSpec(asset_id=asset_id, duration_seconds=30.0)])
    edl = _edl(_clip(asset_id=asset_id, source_start=0, source_end=5), version=2)

    report = validator.validate(edl, previous_version=2)

    assert report.ok is False
    assert any(i.code == "version_not_monotonic" for i in report.issues)


def test_monotonic_version_ok() -> None:
    asset_id = uuid4()
    validator = EdlValidator([AssetSpec(asset_id=asset_id, duration_seconds=30.0)])
    edl = _edl(_clip(asset_id=asset_id, source_start=0, source_end=5), version=3)

    report = validator.validate(edl, previous_version=2)

    assert report.ok is True


# --- multi-issue reporting -----------------------------------------------


def test_collects_multiple_issues_and_locations() -> None:
    good_id = uuid4()
    validator = EdlValidator([AssetSpec(asset_id=good_id, duration_seconds=10.0)])

    bad_clips = [
        _clip(asset_id=uuid4(), source_start=0, source_end=5),  # asset_not_found
        _clip(asset_id=good_id, source_start=0, source_end=20),  # past duration
    ]

    report = validator.validate(_edl(*bad_clips))

    assert report.ok is False
    locations = {i.location for i in report.issues}
    assert "timeline[0].clips[0]" in locations
    assert "timeline[0].clips[1]" in locations
    assert {i.severity for i in report.issues} == {ValidationSeverity.ERROR}


# --- ORM bridge ---------------------------------------------------------


class _FakeAssetRow:
    def __init__(self, asset_id: UUID, analysis: dict) -> None:
        self.id = asset_id
        self.analysis = analysis


def test_from_asset_row_reads_duration_from_analysis() -> None:
    asset_id = uuid4()
    spec = AssetSpec.from_asset_row(
        _FakeAssetRow(asset_id, {"duration_seconds": 12.5})
    )
    assert spec.asset_id == asset_id
    assert spec.duration_seconds == pytest.approx(12.5)


def test_from_asset_row_defaults_to_zero_when_unanalysed() -> None:
    asset_id = uuid4()
    spec_none = AssetSpec.from_asset_row(_FakeAssetRow(asset_id, None))  # type: ignore[arg-type]
    spec_empty = AssetSpec.from_asset_row(_FakeAssetRow(asset_id, {}))
    assert spec_none.duration_seconds == 0.0
    assert spec_empty.duration_seconds == 0.0
