"""Unit tests for :mod:`app.pipeline.transcriber`.

We do not load a real Whisper model here. Coverage is the
:class:`StubTranscriber` and the missing-path failure on
:class:`WhisperTranscriber`. Real-model coverage lives in a future
integration test behind an env guard so CI does not pull the
weights.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.contracts import TranscriptSegment
from app.core.errors import ExternalServiceError
from app.pipeline.transcriber import StubTranscriber, WhisperTranscriber

# --- StubTranscriber -----------------------------------------------------


async def test_stub_returns_canned_segments(tmp_path: Path) -> None:
    canned = [
        TranscriptSegment(
            start_seconds=0.0,
            end_seconds=2.5,
            text="שלום עולם",
            language="he",
        ),
        TranscriptSegment(
            start_seconds=2.5,
            end_seconds=5.0,
            text="זה ניסיון",
            language="he",
        ),
    ]
    transcriber = StubTranscriber(segments=canned)

    segments = await transcriber.transcribe(tmp_path / "anything.mp4")

    assert len(segments) == 2
    assert segments[0].text == "שלום עולם"
    assert segments[1].language == "he"


async def test_stub_returns_empty_list_by_default(tmp_path: Path) -> None:
    transcriber = StubTranscriber()
    assert await transcriber.transcribe(tmp_path / "anything.mp4") == []


async def test_stub_ignores_path_and_language(tmp_path: Path) -> None:
    """The stub never touches the filesystem; both args are advisory."""
    transcriber = StubTranscriber(
        segments=[
            TranscriptSegment(start_seconds=0, end_seconds=1, text="x", language="en"),
        ],
    )
    out = await transcriber.transcribe(Path("/no/such/file.mp4"), language="es")
    assert out[0].language == "en"


# --- WhisperTranscriber --------------------------------------------------


async def test_whisper_raises_external_service_error_when_path_missing() -> None:
    with pytest.raises(ExternalServiceError, match="does not exist"):
        await WhisperTranscriber().transcribe(Path("/no/such/file.mp4"))
