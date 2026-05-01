"""Unit tests for :class:`app.pipeline.renderer.FFmpegRenderer`.

We do not invoke a real ``ffmpeg`` here - that's an integration test
concern. These cases pin down command construction and the
``NullRenderer`` smoke path.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.contracts import (
    AudioPlan,
    ClipReference,
    EditDecisionList,
    OutputSpec,
    TimelineClip,
    Track,
)
from app.core.errors import ExternalServiceError
from app.pipeline.renderer import FFmpegRenderer, NullRenderer, RenderInput


def _edl(*clips: TimelineClip) -> EditDecisionList:
    return EditDecisionList(
        version=1,
        timeline=[Track(kind="video", clips=list(clips))],
        audio=AudioPlan(),
        output=OutputSpec(width=1920, height=1080, fps=30, container="mp4"),
    )


def _clip(asset_id, start: float, end: float, timeline_start: float = 0.0):
    return TimelineClip(
        clip=ClipReference(asset_id=asset_id, source_start_seconds=start, source_end_seconds=end),
        timeline_start_seconds=timeline_start,
    )


async def test_null_renderer_writes_placeholder_and_reports_duration(
    tmp_path: Path,
) -> None:
    asset_id = uuid4()
    edl = _edl(_clip(asset_id, 0, 4), _clip(asset_id, 4, 6, timeline_start=4))
    out = tmp_path / "x.mp4"

    result = await NullRenderer().render(
        RenderInput(edl=edl, asset_paths={asset_id: tmp_path / "src.mp4"}, output_path=out)
    )

    assert out.exists()
    assert out.read_bytes() == b"NULL_RENDERER"
    assert result.duration_seconds == pytest.approx(6.0)
    assert result.container == "mp4"


def test_ffmpeg_command_includes_input_per_clip_and_concat_filter(
    tmp_path: Path,
) -> None:
    asset_a, asset_b = uuid4(), uuid4()
    edl = _edl(
        _clip(asset_a, 0.5, 3.5, timeline_start=0),
        _clip(asset_b, 1.0, 2.5, timeline_start=3),
    )
    payload = RenderInput(
        edl=edl,
        asset_paths={
            asset_a: tmp_path / "a.mp4",
            asset_b: tmp_path / "b.mp4",
        },
        output_path=tmp_path / "out.mp4",
    )

    cmd = FFmpegRenderer().debug_command(payload)

    # Two -i inputs in order, with the right -ss / -t pair before each.
    assert "-ss 0.500 -t 3.000 -i" in cmd
    assert "-ss 1.000 -t 1.500 -i" in cmd
    # Filter graph splices both inputs.
    assert "concat=n=2:v=1:a=1[outv][outa]" in cmd
    # Output spec carried over.
    assert "-r 30" in cmd
    assert "-s 1920x1080" in cmd
    assert "out.mp4" in cmd


def test_ffmpeg_command_rejects_missing_asset(tmp_path: Path) -> None:
    asset_id = uuid4()
    edl = _edl(_clip(asset_id, 0, 1))
    payload = RenderInput(edl=edl, asset_paths={}, output_path=tmp_path / "out.mp4")

    with pytest.raises(ExternalServiceError, match="missing asset"):
        FFmpegRenderer().debug_command(payload)


def test_ffmpeg_command_rejects_empty_video_track(tmp_path: Path) -> None:
    edl = EditDecisionList(
        version=1,
        timeline=[Track(kind="video", clips=[])],
        audio=AudioPlan(),
        output=OutputSpec(),
    )
    payload = RenderInput(edl=edl, asset_paths={}, output_path=tmp_path / "out.mp4")

    with pytest.raises(ExternalServiceError, match="no video clips"):
        FFmpegRenderer().debug_command(payload)


async def test_ffmpeg_renderer_translates_missing_binary_into_external_service_error(
    tmp_path: Path,
) -> None:
    asset_id = uuid4()
    edl = _edl(_clip(asset_id, 0, 1))
    payload = RenderInput(
        edl=edl,
        asset_paths={asset_id: tmp_path / "src.mp4"},
        output_path=tmp_path / "out.mp4",
    )

    with pytest.raises(ExternalServiceError):
        # Use a binary name that definitely doesn't exist.
        await FFmpegRenderer(ffmpeg_binary="ffmpeg-does-not-exist-xyz").render(payload)
