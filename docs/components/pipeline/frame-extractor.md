# Component: Pipeline / Frame Extractor

> Pulls a small list of evenly-spaced sample frames out of a video.
> The Vision Analyzer agent reads these frames; the extractor itself
> is a pure ``ffmpeg`` job.

## Purpose

Vision-capable LLM calls are billed per pixel. Sending the entire
video is wasteful and slow; sending nothing is useless. The
extractor produces a handful of representative frames at known
timestamps, downscaled to a vision-friendly resolution, and hands
them to :class:`AssetAnalysisService` to attach to the agent call.

## Public interface

```python
@dataclass(slots=True, frozen=True)
class ExtractedFrame:
    timestamp_seconds: float
    data: bytes
    media_type: str = "image/jpeg"

class FrameExtractor(Protocol):
    async def extract(
        self, path: Path, *, count: int, duration_seconds: float
    ) -> list[ExtractedFrame]: ...

class FFmpegFrameExtractor(FrameExtractor):
    def __init__(
        self,
        *,
        ffmpeg_binary: str = "ffmpeg",
        scale_width: int = 768,
        jpeg_quality: int = 4,
    ) -> None: ...

class StubFrameExtractor(FrameExtractor):
    """Test/dev: returns ``count`` placeholder frames with distinct bytes."""
```

## How `FFmpegFrameExtractor` works

For each timestamp, one ``ffmpeg`` invocation:

```
ffmpeg -y -loglevel error \
       -ss <timestamp> -i <path> \
       -frames:v 1 \
       -vf scale=768:-2 \
       -q:v 4 \
       <scratch>/frame_<i>.jpg
```

Why one invocation per frame:

- ``-ss`` before ``-i`` is the fast input seek - cheap on most
  containers.
- One invocation per frame keeps the command trivially debuggable
  (no batched filtergraph to reason about).
- The cost is a few extra forks; for a 6-frame extraction the wall-
  clock difference vs. a single multi-output invocation is
  negligible.

``scale=768:-2`` keeps aspect ratio while bounding the long edge -
big enough for vision reasoning, small enough to keep token cost in
check. ``-q:v 4`` is "high quality" on FFmpeg's 1 (best) - 31
(worst) JPEG scale.

## Timestamp choice

:func:`_evenly_spaced_timestamps` picks ``count`` timestamps spread
across the video, with a 10% margin on each side. With ``count=4``
and a 10s clip you get ``[1.0, 3.667, 6.333, 9.0]``. Avoiding the
very edges sidesteps encoder ramp-up artefacts and credit cards/
title cards that frequently hide there.

## Errors

Every failure raises :class:`ExternalServiceError`:

| Cause                       | When                                         |
| --------------------------- | -------------------------------------------- |
| Path does not exist         | caller didn't write the file before extracting |
| ``ffmpeg`` binary missing   | container missing the binary                 |
| ``ffmpeg`` exits non-zero   | unsupported codec, malformed timestamp       |
| Output file not produced    | something went silently wrong inside ffmpeg  |

## How to test

- Unit: ``backend/tests/test_frame_extractor.py`` covers the
  pure timestamp helper, :class:`StubFrameExtractor` payload
  uniqueness, missing path, and missing binary.
- Integration (later): a smoke test against a real sample clip
  behind an env guard.

## Change log notes

- The extractor's scratch directory is removed on every exit path -
  partial frames are never observable to other components.
- ``count`` defaults are owned by the caller (``AssetAnalysisService``
  uses 6); the extractor itself does not opine on a sensible default.
