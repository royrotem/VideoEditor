"""Unit tests for :mod:`app.pipeline.frame_extractor`.

We do not invoke real ``ffmpeg`` here. Coverage is the timestamp
helper (a pure function), :class:`StubFrameExtractor`, and the
binary-missing failure path on :class:`FFmpegFrameExtractor`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import ExternalServiceError
from app.pipeline.frame_extractor import (
    FFmpegFrameExtractor,
    StubFrameExtractor,
    _evenly_spaced_timestamps,
)

# --- timestamp helper ---------------------------------------------------


def test_timestamps_avoid_edges_for_more_than_one_frame() -> None:
    timestamps = _evenly_spaced_timestamps(4, 10.0)

    # 10% margin on each side => first at 1.0, last at 9.0.
    assert timestamps[0] == pytest.approx(1.0)
    assert timestamps[-1] == pytest.approx(9.0)
    # Equally spaced.
    from itertools import pairwise

    deltas = [b - a for a, b in pairwise(timestamps)]
    assert all(abs(d - deltas[0]) < 1e-6 for d in deltas)


def test_timestamps_returns_midpoint_for_single_frame() -> None:
    assert _evenly_spaced_timestamps(1, 4.0) == [2.0]


def test_timestamps_handles_zero_count() -> None:
    assert _evenly_spaced_timestamps(0, 10.0) == []


def test_timestamps_collapses_to_zero_when_duration_too_short() -> None:
    # 90% of 0.0 is 0.0 — fall back to zeros (the extractor will simply
    # ask for one frame at 0s, and FFmpeg can grab the very first
    # frame). What we DON'T want is a ZeroDivisionError.
    timestamps = _evenly_spaced_timestamps(3, 0.0)
    assert timestamps == [0.0, 0.0, 0.0]


# --- StubFrameExtractor --------------------------------------------------


async def test_stub_extractor_returns_count_frames_with_distinct_payloads(
    tmp_path: Path,
) -> None:
    extractor = StubFrameExtractor()

    frames = await extractor.extract(tmp_path / "video.mp4", count=3, duration_seconds=6.0)

    assert len(frames) == 3
    timestamps = [f.timestamp_seconds for f in frames]
    assert timestamps[0] < timestamps[1] < timestamps[2]
    payloads = {f.data for f in frames}
    assert len(payloads) == 3
    assert all(f.media_type == "image/jpeg" for f in frames)


async def test_stub_extractor_returns_empty_for_zero_count(tmp_path: Path) -> None:
    extractor = StubFrameExtractor()

    assert await extractor.extract(tmp_path / "x.mp4", count=0, duration_seconds=1) == []


# --- FFmpegFrameExtractor ------------------------------------------------


async def test_ffmpeg_extractor_raises_external_service_error_when_path_missing() -> None:
    with pytest.raises(ExternalServiceError, match="does not exist"):
        await FFmpegFrameExtractor().extract(Path("/no/such/file.mp4"), count=1, duration_seconds=1)


async def test_ffmpeg_extractor_raises_when_binary_missing(
    tmp_path: Path,
) -> None:
    fake_video = tmp_path / "video.mp4"
    fake_video.write_bytes(b"\x00")

    with pytest.raises(ExternalServiceError):
        await FFmpegFrameExtractor(ffmpeg_binary="ffmpeg-does-not-exist-xyz").extract(
            fake_video, count=1, duration_seconds=1
        )
