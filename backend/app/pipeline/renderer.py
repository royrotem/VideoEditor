"""Renderer protocol + a default FFmpeg-backed implementation.

The renderer is the deterministic, single-purpose component that
takes an :class:`EditDecisionList` plus a map of asset id → local
file path and writes a single rendered file to a target path. It does
**no** I/O against the object store and **no** database writes - the
:class:`~app.services.render.RenderJobService` is in charge of that.

Two implementations land here:

- :class:`FFmpegRenderer` - production. Spawns ``ffmpeg`` once, builds
  the filtergraph from the EDL, and writes the output file.
- :class:`NullRenderer` - a no-op used in tests and to smoke-test the
  surrounding service plumbing without depending on a real ``ffmpeg``
  binary.
"""

from __future__ import annotations

import asyncio
import contextlib
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.agents.contracts import EditDecisionList
from app.core.errors import ExternalServiceError


@dataclass(slots=True, frozen=True)
class RenderInput:
    """Everything the renderer needs to produce one file.

    ``asset_paths`` maps each asset id referenced by the EDL to a
    local readable file. The :class:`RenderJobService` is responsible
    for pulling assets from the object store onto disk before calling
    the renderer.
    """

    edl: EditDecisionList
    asset_paths: dict[UUID, Path]
    output_path: Path


@dataclass(slots=True, frozen=True)
class RenderResult:
    """Outcome of a render: the file plus a few useful facts.

    The service layer translates this into a render-job row and a
    publish-ready :class:`StoredObject`.
    """

    output_path: Path
    duration_seconds: float
    container: str  # "mp4" / "mov" - mirrors EditDecisionList.output.container


class Renderer(Protocol):
    """Renderer interface every implementation conforms to."""

    async def render(self, payload: RenderInput) -> RenderResult:
        """Render ``payload`` to ``payload.output_path``.

        Raises :class:`ExternalServiceError` on any rendering failure.
        Implementations must clean up partial output files before
        re-raising so the caller never observes a half-written render.
        """


class NullRenderer(Renderer):
    """Test/development renderer that writes a tiny placeholder file.

    Useful for exercising the surrounding service code without a real
    ``ffmpeg`` install. Computes the expected total duration from the
    EDL so callers can still assert on it.
    """

    async def render(self, payload: RenderInput) -> RenderResult:
        payload.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload.output_path.write_bytes(b"NULL_RENDERER")
        duration = _expected_duration(payload.edl)
        return RenderResult(
            output_path=payload.output_path,
            duration_seconds=duration,
            container=payload.edl.output.container,
        )


class FFmpegRenderer(Renderer):
    """Production renderer that drives ``ffmpeg`` via ``asyncio``.

    Builds one ``ffmpeg`` invocation per EDL: input files in EDL order,
    a ``concat`` filter to splice the clips, and an encoder configured
    by :class:`~app.agents.contracts.OutputSpec`. Audio handling stays
    minimal (passthrough or silent) - the Audio Engineer agent will
    drive a richer audio graph in a later branch.
    """

    def __init__(self, *, ffmpeg_binary: str = "ffmpeg") -> None:
        self._ffmpeg = ffmpeg_binary

    async def render(self, payload: RenderInput) -> RenderResult:
        args = self._build_command(payload)
        try:
            process = await asyncio.create_subprocess_exec(
                self._ffmpeg,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await process.communicate()
        except FileNotFoundError as exc:  # ffmpeg not installed
            raise ExternalServiceError(f"ffmpeg binary not found: {self._ffmpeg}") from exc
        except OSError as exc:
            raise ExternalServiceError(f"failed to invoke ffmpeg: {exc}") from exc

        if process.returncode != 0:
            self._cleanup_partial(payload.output_path)
            tail = stderr.decode("utf-8", errors="replace")[-2_000:]
            raise ExternalServiceError(f"ffmpeg exited with code {process.returncode}: {tail}")

        if not payload.output_path.exists():
            raise ExternalServiceError("ffmpeg reported success but output file is missing")

        return RenderResult(
            output_path=payload.output_path,
            duration_seconds=_expected_duration(payload.edl),
            container=payload.edl.output.container,
        )

    def _build_command(self, payload: RenderInput) -> list[str]:
        """Build the ffmpeg argv for one EDL.

        Each timeline clip becomes ``-ss <source_start> -t <length> -i <path>``
        followed by a single ``concat`` filter that splices them. We
        rebuild the command from scratch every call so it is trivially
        debuggable - no hidden state, just argv.
        """
        ordered_clips = [
            clip for track in payload.edl.timeline if track.kind == "video" for clip in track.clips
        ]
        if not ordered_clips:
            raise ExternalServiceError("EDL has no video clips to render")

        spec = payload.edl.output
        args: list[str] = ["-y", "-loglevel", "error"]

        for clip in ordered_clips:
            ref = clip.clip
            source_path = payload.asset_paths.get(ref.asset_id)
            if source_path is None:
                raise ExternalServiceError(f"render input missing asset {ref.asset_id}")
            length = max(ref.source_end_seconds - ref.source_start_seconds, 0.001)
            args.extend(
                [
                    "-ss",
                    f"{ref.source_start_seconds:.3f}",
                    "-t",
                    f"{length:.3f}",
                    "-i",
                    str(source_path),
                ]
            )

        # filter_complex: concat the N inputs into one v/a stream pair.
        n = len(ordered_clips)
        concat_inputs = "".join(f"[{i}:v:0][{i}:a:0?]" for i in range(n))
        filter_complex = f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]"
        args.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[outv]",
                "-map",
                "[outa]",
                "-r",
                str(spec.fps),
                "-s",
                f"{spec.width}x{spec.height}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(payload.output_path),
            ]
        )
        return args

    @staticmethod
    def _cleanup_partial(path: Path) -> None:
        """Remove a half-written file so the caller never observes it.

        Best effort - if we can't remove it, the failure message
        already tells the user something went wrong.
        """
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)

    def debug_command(self, payload: RenderInput) -> str:
        """Return a copy-pasteable shell version of the ffmpeg command.

        Handy in tests and in incident debugging.
        """
        return shlex.join([self._ffmpeg, *self._build_command(payload)])


def _expected_duration(edl: EditDecisionList) -> float:
    """Sum the lengths of clips on the longest video track."""
    durations: list[float] = []
    for track in edl.timeline:
        if track.kind != "video":
            continue
        track_total = sum(
            max(c.clip.source_end_seconds - c.clip.source_start_seconds, 0.0) for c in track.clips
        )
        durations.append(track_total)
    return max(durations, default=0.0)
