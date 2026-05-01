# Component: Pipeline / Probe

> Deterministic measurement of an uploaded media file. Reads the few
> facts every downstream stage depends on and lets the LLM-backed
> Vision Analyzer fill in the qualitative ones later.

## Purpose

Every uploaded asset goes through the probe before anything else
touches it: the EDL Validator needs the duration to refuse
out-of-range clips; the renderer needs ``has_audio`` to build the
right ``concat`` filter; the Creative Director's ``ASSET_FACTS``
header needs duration for plausible time budgets.

The probe is a pure function: ``Path → ProbeResult``. No DB, no
object store, no LLM. The orchestration layer
(:doc:`AssetAnalysisService <../services/analysis>`) wraps it with
download / persist / status updates.

## Public interface

```python
@dataclass(slots=True, frozen=True)
class ProbeResult:
    duration_seconds: float
    width: int | None
    height: int | None
    has_audio: bool
    container_format: str | None

class Probe(Protocol):
    async def probe(self, path: Path) -> ProbeResult: ...

class FFprobeProbe(Probe):
    def __init__(self, *, ffprobe_binary: str = "ffprobe") -> None: ...

class StubProbe(Probe):
    """Test/dev: returns canned ProbeResult regardless of input path."""
```

## How `FFprobeProbe` works

One ``ffprobe`` invocation per file, JSON output:

```
ffprobe -v error -print_format json -show_format -show_streams <path>
```

Duration is read from ``format.duration`` (more accurate for
containers with VFR / B-frames) and falls back to the first video
stream's duration. Resolution comes from the first video stream.
Audio presence is "is there a stream with ``codec_type == audio``".
Everything else is ignored - keeping the parser narrow makes it
robust to the shape variations across containers.

## Errors

Every failure raises :class:`ExternalServiceError`:

| Cause                    | When                                              |
| ------------------------ | ------------------------------------------------- |
| Path does not exist      | caller didn't write the file before probing       |
| ``ffprobe`` not found    | binary missing from the container                 |
| ``ffprobe`` exits non-zero | malformed file, unsupported codec               |
| Output is not JSON       | ``ffprobe`` printed something unexpected          |

## How to test

- Unit: ``backend/tests/test_probe.py`` covers the JSON parser
  (which is a pure function), :class:`StubProbe`, and the
  missing-binary / missing-path failures.
- Integration (later): a smoke test against a real sample clip
  behind an env guard.

## Change log notes

- **The probe owns only deterministic facts.** Shot detection,
  transcription, and qualitative summaries belong to a different
  pass (Vision Analyzer agent + Whisper) which writes additional
  keys to ``asset.analysis``. The probe is allowed to overwrite the
  keys it owns; the analysis service merge step keeps everything
  else.
- ``container_format`` is informational - the renderer reads
  ``edl.output.container``, not the source's container.
