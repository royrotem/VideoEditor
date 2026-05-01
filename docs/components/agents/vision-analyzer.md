# Component: Agents / Vision Analyzer

> Vision-capable Claude agent. Reads the deterministic facts about an
> asset (duration, resolution, ``has_audio``) plus a small number of
> sample frames, and produces qualitative AssetFacts: a Hebrew
> summary and per-shot descriptions.

## Purpose

The FFprobe stage answers "how long is the clip and what's its
resolution"; the Vision Analyzer answers "what is *in* the clip".
Its output rounds out the :class:`AssetFacts` payload so the
Creative Director can talk about footage in words instead of ids.

The deterministic and qualitative halves are kept separate on
purpose: probe results are fast, free, and replayable; the LLM pass
is slow, costs tokens, and may be re-run when the prompt evolves.
Each half can be regenerated without invalidating the other.

## Public interface

```python
class VisionAnalysisInput(BaseModel):
    asset_id: UUID
    duration_seconds: float
    width: int | None
    height: int | None
    has_audio: bool

class VisionAnalysisOutput(BaseModel):
    summary: str
    shots: list[Shot]   # see app.agents.contracts.Shot

class VisionAnalyzer(Agent[VisionAnalysisInput, VisionAnalysisOutput]):
    name = "vision_analyzer"
    model = "claude-sonnet-4-6"
    output_model = VisionAnalysisOutput

    async def run_with_frames(
        self, input_payload: VisionAnalysisInput, frames: list[ImageBlock]
    ) -> VisionAnalysisOutput: ...

def merge_into_asset_facts(
    *, base: VisionAnalysisInput, output: VisionAnalysisOutput
) -> AssetFacts: ...
```

## Inputs

- :class:`VisionAnalysisInput` - the deterministic facts.
- ``frames`` - a list of :class:`ImageBlock` instances, the raw
  bytes of evenly-spaced sample frames extracted from the video.
  The transport base64-encodes them per request; the agent does
  not store them between calls.

The system prompt tells the model the frames are spaced evenly from
``0s`` to ``duration_seconds`` so it can correlate timestamps to
images.

## Outputs

A :class:`VisionAnalysisOutput`. Use :func:`merge_into_asset_facts`
to compose the deterministic + qualitative halves into a complete
:class:`AssetFacts`.

## Image support in the LLM client

This is the first agent that uses Claude's vision capability. The
plumbing changes are tiny:

- :class:`LLMMessage` gained an ``images: list[ImageBlock]`` field
  defaulting to empty.
- :class:`AnthropicLLMClient` renders messages with images as a list
  of ``image`` content blocks followed by the text - the wire shape
  the Messages API documents for vision models. Messages without
  images stay on the plain-string form so the on-the-wire diff is
  zero for non-vision agents.

## Dependencies

- :class:`Agent` (JSON parsing, schema validation).
- :data:`VISION_ANALYZER_SYSTEM_PROMPT`.

## Errors

| Error                  | When                                              |
| ---------------------- | ------------------------------------------------- |
| `ExternalServiceError` | non-JSON reply or schema mismatch                 |

## How to test

- ``backend/tests/test_vision_analyzer.py`` covers the
  message-rendering switch (text-only vs. images), happy path,
  no-frames variant (deterministic-only), schema-validation
  failure, the merge helper, and registry registration.

## Change log notes

- **Frame extraction is not yet wired in.** The agent accepts frames
  through ``run_with_frames``; a follow-up branch will add a
  :class:`FrameExtractor` (FFmpeg-backed) and extend
  :class:`AssetAnalysisService` to call the agent right after the
  probe.
- Sonnet 4.6 (not Opus) is the default model: the task is short,
  schema-bound, and benefits more from speed than from extra
  reasoning depth. Re-evaluate if visual quality regresses on hard
  scenes.
