"""Unit tests for :class:`app.pipeline.probe`.

We do not invoke a real ``ffprobe`` here. The tests exercise the JSON
parser directly (it's a pure function of dict → ProbeResult) and the
:class:`StubProbe`. End-to-end ``ffprobe`` coverage is an integration
test concern.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import ExternalServiceError
from app.pipeline.probe import (
    FFprobeProbe,
    ProbeResult,
    StubProbe,
    _parse_ffprobe_payload,
)


def _ffprobe_payload(
    *,
    duration: str | None = "12.5",
    width: int | None = 1920,
    height: int | None = 1080,
    has_audio: bool = True,
    format_name: str | None = "mov,mp4,m4a,3gp,3g2,mj2",
) -> dict:
    """Build a minimal ffprobe -show_format -show_streams JSON dict."""
    streams = []
    if width is not None and height is not None:
        streams.append(
            {
                "codec_type": "video",
                "width": width,
                "height": height,
                "duration": duration,
            }
        )
    if has_audio:
        streams.append({"codec_type": "audio"})
    return {
        "format": {"duration": duration, "format_name": format_name},
        "streams": streams,
    }


def test_parser_extracts_duration_resolution_and_audio_flag() -> None:
    result = _parse_ffprobe_payload(_ffprobe_payload())

    assert result == ProbeResult(
        duration_seconds=12.5,
        width=1920,
        height=1080,
        has_audio=True,
        container_format="mov,mp4,m4a,3gp,3g2,mj2",
    )


def test_parser_falls_back_to_video_stream_duration_when_format_missing() -> None:
    payload = _ffprobe_payload(duration=None)
    payload["format"]["duration"] = None
    payload["streams"][0]["duration"] = "7.25"

    result = _parse_ffprobe_payload(payload)

    assert result.duration_seconds == pytest.approx(7.25)


def test_parser_marks_no_audio_when_no_audio_stream() -> None:
    result = _parse_ffprobe_payload(_ffprobe_payload(has_audio=False))
    assert result.has_audio is False


def test_parser_handles_audio_only_file() -> None:
    payload = _ffprobe_payload(width=None, height=None, has_audio=True)
    # Audio-only: drop the video stream entirely.
    payload["streams"] = [{"codec_type": "audio", "duration": "5.0"}]

    result = _parse_ffprobe_payload(payload)

    assert result.width is None
    assert result.height is None
    assert result.has_audio is True


def test_parser_returns_zero_duration_for_empty_payload() -> None:
    result = _parse_ffprobe_payload({})
    assert result.duration_seconds == 0.0
    assert result.width is None
    assert result.height is None
    assert result.has_audio is False


async def test_stub_probe_returns_canned_result(tmp_path: Path) -> None:
    probe = StubProbe(duration_seconds=42.0, width=720, height=1280, has_audio=False)

    result = await probe.probe(tmp_path / "anything.mp4")

    assert result.duration_seconds == 42.0
    assert result.width == 720
    assert result.height == 1280
    assert result.has_audio is False


async def test_ffprobe_translates_missing_binary_into_external_service_error(
    tmp_path: Path,
) -> None:
    fake_file = tmp_path / "x.mp4"
    fake_file.write_bytes(b"\x00")

    with pytest.raises(ExternalServiceError):
        await FFprobeProbe(ffprobe_binary="ffprobe-does-not-exist-xyz").probe(
            fake_file
        )


async def test_ffprobe_raises_when_path_missing() -> None:
    with pytest.raises(ExternalServiceError, match="does not exist"):
        await FFprobeProbe().probe(Path("/no/such/file.mp4"))
