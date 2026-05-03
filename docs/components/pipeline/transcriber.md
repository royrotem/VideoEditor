# Component: Pipeline / Transcriber

> Audio transcription via OpenAI Whisper. Fills the ``transcript``
> field of :class:`AssetFacts` so the Creative Director can reason
> about *what's said* in a clip, not only *what's seen*.

## Purpose

The probe answers "how long, how big, is there audio". The Vision
Analyzer answers "what's in the picture". The transcriber answers
"what is being said". All three feed the same ``asset.analysis``
JSON blob; the Creative Director reads the merged result.

The transcriber is a pure function ``Path → list[TranscriptSegment]``.
No DB, no object store, no LLM other than Whisper itself. The
orchestration layer (:doc:`AssetAnalysisService <../services/analysis>`)
wraps it with download / persist / status updates.

## Public interface

```python
class Transcriber(Protocol):
    async def transcribe(
        self, path: Path, *, language: str | None = None
    ) -> list[TranscriptSegment]: ...

class WhisperTranscriber(Transcriber):
    def __init__(
        self,
        *,
        model_name: str = "small",
        default_language: str | None = "he",
    ) -> None: ...

class StubTranscriber(Transcriber):
    """Test/dev: returns canned segments regardless of input."""
```

``TranscriptSegment`` is the same Pydantic model the agent contracts
already use - ``start_seconds``, ``end_seconds``, ``text``,
``language``.

## How `WhisperTranscriber` works

- Lazy model load: the (~250 MB for ``small``, more for larger
  variants) Whisper weights are pulled only when the first
  ``transcribe`` call happens, then reused for every subsequent call.
  A plain ``threading.Lock`` serialises the load so concurrent first
  calls do not pay the cost twice.
- Blocking inside a thread: Whisper is synchronous; the wrapper
  invokes it via :func:`asyncio.to_thread` so the FastAPI event loop
  stays unblocked.
- Default language: Hebrew (``"he"``); callers can override per call.
- ``fp16=False`` so the same code path works on CPU machines.

The transcriber **defaults to the ``small`` model**, which is the
cheapest variant that produces usable Hebrew transcripts on a
CPU. Pass ``model_name="medium"`` (or ``"large-v3"`` on a GPU box)
when accuracy matters more than throughput.

## When the orchestrator runs it

:meth:`AssetAnalysisService._maybe_transcribe` is best-effort and
short-circuits when:

- the transcriber is not configured (e.g. tests),
- the probe reports ``has_audio == False``,
- the probe reports zero duration.

A failure raised by the transcriber is logged as a warning; the
deterministic half of the analysis is still saved and the asset
still becomes ``ready``. This mirrors the vision-pass policy.

## Errors

Every failure raises :class:`ExternalServiceError`:

| Cause                       | When                                         |
| --------------------------- | -------------------------------------------- |
| Path does not exist         | caller didn't write the file before transcribing |
| Model load failed           | weights download / disk / RAM error          |
| Whisper raised              | unsupported codec, broken audio              |

## How to test

- Unit: ``backend/tests/test_transcriber.py`` covers
  :class:`StubTranscriber` and the missing-path failure on
  :class:`WhisperTranscriber`.
- Integration: ``backend/tests/test_analysis_service.py`` exercises
  the orchestration layer (``AssetAnalysisService``) with a
  :class:`StubTranscriber` so the merge + skip-on-no-audio + failure
  paths are all covered.
- A real-Whisper smoke test will land later behind an env guard so
  CI does not pull the weights on every run.

## Change log notes

- The transcriber writes ``asset.analysis["transcript"]`` as a list
  of ``{start_seconds, end_seconds, text, language}`` dicts. The
  ChatService lifts that JSON straight into
  :class:`AssetFacts.transcript` when assembling the
  ``ASSET_FACTS`` block for the Creative Director - the agents do
  not need to know the transcript came from Whisper.
- The model is loaded once per **process**. If you scale workers
  horizontally each one pays the load cost on its first task.
  Memory usage is proportional to the model size; ``small`` is
  ~1 GB resident, ``medium`` is ~2.5 GB, ``large-v3`` is ~5 GB.
