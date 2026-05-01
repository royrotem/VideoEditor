"""Asset probing - deterministic measurement of an uploaded media file.

This is the first step every uploaded asset goes through. It extracts
the small set of facts the rest of the pipeline depends on:

- ``duration_seconds`` (used by :class:`EdlValidator` to refuse
  out-of-range clip references)
- ``width`` / ``height`` (used by the renderer for letterboxing /
  scaling decisions)
- ``has_audio`` (drives the ``concat`` filter built by
  :class:`FFmpegRenderer`)

The richer ``AssetFacts`` payload (shots, transcript, summary) is
filled in later by the Claude-backed Vision Analyzer agent. The probe
keeps that contract intact - it just leaves those fields empty.

Two implementations land here:

- :class:`FFprobeProbe` - production. Spawns ``ffprobe`` once and
  parses its JSON output.
- :class:`StubProbe` - test/development. Returns canned values so the
  surrounding service plumbing can be tested without ``ffprobe``
  installed.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.core.errors import ExternalServiceError


@dataclass(slots=True, frozen=True)
class ProbeResult:
    """Deterministic facts about a single media file."""

    duration_seconds: float
    width: int | None
    height: int | None
    has_audio: bool
    container_format: str | None = None


class Probe(Protocol):
    """Probe interface every implementation conforms to."""

    async def probe(self, path: Path) -> ProbeResult:
        """Read ``path`` and return a :class:`ProbeResult`.

        Implementations raise :class:`ExternalServiceError` on any
        failure (binary missing, malformed file, parse error). The
        callers translate that into an asset ``status = failed``.
        """


class StubProbe(Probe):
    """Static :class:`Probe` for tests and dev environments.

    Returns the same :class:`ProbeResult` regardless of the input
    path. Use a fresh instance per test - the values are constructor
    arguments so each test pins the facts it asserts on.
    """

    def __init__(
        self,
        *,
        duration_seconds: float = 0.0,
        width: int | None = 1920,
        height: int | None = 1080,
        has_audio: bool = True,
        container_format: str | None = "mp4",
    ) -> None:
        self._result = ProbeResult(
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            has_audio=has_audio,
            container_format=container_format,
        )

    async def probe(self, path: Path) -> ProbeResult:
        return self._result


class FFprobeProbe(Probe):
    """Production probe driven by ``ffprobe`` over ``asyncio``.

    One ``ffprobe`` invocation per file: ``-show_format`` for duration
    + container, ``-show_streams`` for video + audio metadata, JSON
    output. The wall-clock cost is dominated by the subprocess fork,
    so chaining multiple probes is a future concern (and easily moved
    onto Celery workers without touching this module).
    """

    def __init__(self, *, ffprobe_binary: str = "ffprobe") -> None:
        self._ffprobe = ffprobe_binary

    async def probe(self, path: Path) -> ProbeResult:
        if not path.exists():
            raise ExternalServiceError(f"asset path does not exist: {path}")

        args = [
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                self._ffprobe,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
        except FileNotFoundError as exc:
            raise ExternalServiceError(
                f"ffprobe binary not found: {self._ffprobe}"
            ) from exc
        except OSError as exc:
            raise ExternalServiceError(f"failed to invoke ffprobe: {exc}") from exc

        if process.returncode != 0:
            tail = stderr.decode("utf-8", errors="replace")[-2_000:]
            raise ExternalServiceError(
                f"ffprobe exited with code {process.returncode}: {tail}"
            )

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ExternalServiceError(
                f"ffprobe returned invalid JSON: {exc}"
            ) from exc

        return _parse_ffprobe_payload(payload)


def _parse_ffprobe_payload(payload: dict[str, Any]) -> ProbeResult:
    """Translate ``ffprobe -show_format -show_streams`` JSON to a result.

    Resolution is read from the first video stream we encounter;
    duration prefers the ``format`` block (more accurate for
    containers with VFR / B-frames) and falls back to the video
    stream's own duration. Audio presence is a simple "is there a
    stream with codec_type == audio".
    """
    fmt = payload.get("format") or {}
    streams = payload.get("streams") or []

    duration = _coerce_float(fmt.get("duration"))

    video_stream: dict[str, Any] | None = next(
        (s for s in streams if s.get("codec_type") == "video"), None
    )
    audio_stream: dict[str, Any] | None = next(
        (s for s in streams if s.get("codec_type") == "audio"), None
    )

    if duration is None and video_stream is not None:
        duration = _coerce_float(video_stream.get("duration"))
    duration = duration or 0.0

    width = _coerce_int(video_stream.get("width")) if video_stream else None
    height = _coerce_int(video_stream.get("height")) if video_stream else None

    container_format = fmt.get("format_name")

    return ProbeResult(
        duration_seconds=float(duration),
        width=width,
        height=height,
        has_audio=audio_stream is not None,
        container_format=container_format,
    )


def _coerce_float(value: object) -> float | None:
    """Best-effort float conversion that tolerates ``None`` / strings."""
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
