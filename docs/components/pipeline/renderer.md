# Component: Pipeline / Renderer

> The deterministic media-processing component. Takes an EDL plus a
> map of asset id → local file path, returns a single rendered file.

## Purpose

Translate a validated :class:`EditDecisionList` into one playable
output file. The renderer never touches the database, the object
store, or the LLM - the surrounding
:class:`~app.services.render.RenderJobService` is responsible for
that. Keeping the renderer pure makes it trivially testable and
swappable: the same EDL contract can drive a different renderer
backend (cloud transcoder, GPU pipeline) without touching service or
agent code.

## Public interface

```python
@dataclass(slots=True, frozen=True)
class RenderInput:
    edl: EditDecisionList
    asset_paths: dict[UUID, Path]   # local file per asset id
    output_path: Path

@dataclass(slots=True, frozen=True)
class RenderResult:
    output_path: Path
    duration_seconds: float
    container: str  # "mp4" / "mov"

class Renderer(Protocol):
    async def render(self, payload: RenderInput) -> RenderResult: ...

class FFmpegRenderer(Renderer):
    def __init__(self, *, ffmpeg_binary: str = "ffmpeg") -> None: ...
    def debug_command(self, payload: RenderInput) -> str: ...

class NullRenderer(Renderer):
    """Test/dev: writes a placeholder file, reports the expected duration."""
```

## How `FFmpegRenderer` builds its command

Each EDL clip becomes a separate ``-i`` input on a single ``ffmpeg``
invocation, preceded by ``-ss`` (source start) and ``-t`` (length).
A single ``-filter_complex`` graph splices them with ``concat`` and
maps a video + audio output stream. The encoder is configured by
:class:`~app.agents.contracts.OutputSpec` (``width × height``,
``fps``, ``container``); we always emit ``libx264`` + ``yuv420p`` for
broad playback compatibility, with ``+faststart`` for
streaming-friendly mp4. Audio defaults to ``aac``.

Use :meth:`FFmpegRenderer.debug_command` to print the exact shell
command for an EDL - handy when reproducing a failed render.

## Errors

Every failure raises :class:`ExternalServiceError`:

| Cause                                | When                                                |
| ------------------------------------ | --------------------------------------------------- |
| ``ffmpeg`` binary missing            | the configured binary cannot be exec'd              |
| ``ffmpeg`` exits non-zero            | the renderer cleans up the partial output and re-raises with the last 2 KB of stderr |
| ``ffmpeg`` succeeds but no file      | rare - signals a misconfigured filtergraph          |
| EDL has no video clips               | refused before invocation                           |
| `asset_paths` missing an asset id    | refused before invocation                           |

## How to test

- Unit: ``backend/tests/test_renderer.py`` covers
  :class:`NullRenderer`, the argv built by
  :meth:`FFmpegRenderer.debug_command`, and translation of a missing
  binary into :class:`ExternalServiceError`.
- Integration (later): a smoke test that runs ``ffmpeg`` against a
  small fixture clip behind an env guard.

## Change log notes

- The renderer is intentionally small. **Audio strategy beyond
  passthrough lives in a future Audio Engineer pass that rewrites the
  EDL** before this stage runs - keep ``ffmpeg`` orchestration here,
  not policy.
- ``output_path`` must be inside a directory the caller controls.
  :class:`RenderJobService` uses a per-job ``tempfile`` directory and
  removes it after the upload.
