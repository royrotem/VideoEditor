"""Sample-frame extraction.

The :class:`VisionAnalyzer` agent looks at a small list of evenly-
spaced frames pulled from a video. Extracting them is a pure
``ffmpeg`` job - this module owns it so the agent stays free of
subprocess concerns.

Two implementations:

- :class:`FFmpegFrameExtractor` - production. Spawns one ``ffmpeg``
  per frame (cheap because each invocation runs a single ``-ss``
  seek + a single output). Trades a few extra forks for code that
  is trivially debuggable.
- :class:`StubFrameExtractor` - test/dev. Returns canned bytes per
  frame regardless of the input.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.errors import ExternalServiceError


@dataclass(slots=True, frozen=True)
class ExtractedFrame:
    """One sample frame plus the timestamp it came from."""

    timestamp_seconds: float
    data: bytes
    media_type: str = "image/jpeg"


class FrameExtractor(Protocol):
    """Frame extractor interface every implementation conforms to."""

    async def extract(
        self, path: Path, *, count: int, duration_seconds: float
    ) -> list[ExtractedFrame]:
        """Pull ``count`` evenly-spaced frames from ``path``.

        ``count`` is the number of frames the caller wants (typically
        4-8). ``duration_seconds`` is how long the video is - the
        extractor uses it to pick timestamps; it does not re-probe
        the file.

        Implementations raise :class:`ExternalServiceError` on any
        extraction failure.
        """


class StubFrameExtractor(FrameExtractor):
    """Static :class:`FrameExtractor` for tests.

    Returns ``count`` :class:`ExtractedFrame` instances with
    deterministic placeholder bytes. Timestamps reflect the requested
    spacing so callers asserting on them get realistic values.
    """

    def __init__(self, *, payload: bytes = b"STUB-FRAME") -> None:
        self._payload = payload

    async def extract(
        self, path: Path, *, count: int, duration_seconds: float
    ) -> list[ExtractedFrame]:
        if count <= 0:
            return []
        timestamps = _evenly_spaced_timestamps(count, duration_seconds)
        return [
            ExtractedFrame(
                timestamp_seconds=ts,
                data=self._payload + f"-{i}".encode(),
                media_type="image/jpeg",
            )
            for i, ts in enumerate(timestamps)
        ]


class FFmpegFrameExtractor(FrameExtractor):
    """Production :class:`FrameExtractor` driven by ``ffmpeg``."""

    def __init__(
        self,
        *,
        ffmpeg_binary: str = "ffmpeg",
        scale_width: int = 768,
        jpeg_quality: int = 4,
    ) -> None:
        self._ffmpeg = ffmpeg_binary
        # 768px wide is a good cost/quality tradeoff for vision models -
        # large enough to reason about, small enough to keep token cost
        # in check. ``-q:v 4`` is "high quality" on ffmpeg's
        # 1 (best) - 31 (worst) JPEG scale.
        self._scale_width = scale_width
        self._jpeg_quality = jpeg_quality

    async def extract(
        self, path: Path, *, count: int, duration_seconds: float
    ) -> list[ExtractedFrame]:
        if not path.exists():
            raise ExternalServiceError(f"asset path does not exist: {path}")
        if count <= 0:
            return []

        timestamps = _evenly_spaced_timestamps(count, duration_seconds)

        scratch = Path(tempfile.mkdtemp(prefix="frames-"))
        try:
            return [
                ExtractedFrame(
                    timestamp_seconds=ts,
                    data=await self._extract_one(path, ts, scratch / f"frame_{i}.jpg"),
                    media_type="image/jpeg",
                )
                for i, ts in enumerate(timestamps)
            ]
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    async def _extract_one(
        self, path: Path, timestamp_seconds: float, output: Path
    ) -> bytes:
        # ``-ss`` before ``-i`` is the fast input seek; one output
        # frame; rescale to keep the payload small.
        args = [
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp_seconds:.3f}",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={self._scale_width}:-2",
            "-q:v",
            str(self._jpeg_quality),
            str(output),
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                self._ffmpeg,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await process.communicate()
        except FileNotFoundError as exc:
            raise ExternalServiceError(
                f"ffmpeg binary not found: {self._ffmpeg}"
            ) from exc
        except OSError as exc:
            raise ExternalServiceError(f"failed to invoke ffmpeg: {exc}") from exc

        if process.returncode != 0:
            tail = stderr.decode("utf-8", errors="replace")[-2_000:]
            raise ExternalServiceError(
                f"ffmpeg exited with code {process.returncode} extracting "
                f"frame at {timestamp_seconds:.2f}s: {tail}"
            )
        if not output.exists():
            raise ExternalServiceError(
                f"ffmpeg produced no frame at {timestamp_seconds:.2f}s"
            )
        return output.read_bytes()


def _evenly_spaced_timestamps(count: int, duration_seconds: float) -> list[float]:
    """Pick ``count`` timestamps spread across ``[0, duration_seconds]``.

    Avoids the very edges (0 and ``duration``) so the extractor does
    not race the encoder's ramp-up frames. With ``count == 4`` and
    a 10-second clip you get ``[1.0, 3.667, 6.333, 9.0]``.
    """
    if count == 1:
        return [duration_seconds / 2]
    margin = duration_seconds * 0.1
    span = max(duration_seconds - 2 * margin, 0.0)
    if count == 0 or span <= 0:
        return [0.0] * count
    step = span / (count - 1)
    return [margin + i * step for i in range(count)]
