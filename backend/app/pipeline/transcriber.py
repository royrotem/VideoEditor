"""Audio transcription.

Whisper transcribes the audio track of an uploaded asset. The result
fills the ``transcript`` field of :class:`AssetFacts`, which the
Creative Director and any other agent that reads ``ASSET_FACTS`` then
uses verbatim — the agents do not need to know anything about
Whisper or how the timestamps were produced.

Two implementations:

- :class:`WhisperTranscriber` - production. Loads an
  ``openai-whisper`` model on demand and runs it inside a worker
  thread via :func:`asyncio.to_thread` so the event loop is never
  blocked. The model is loaded at most once per process.
- :class:`StubTranscriber` - test/dev. Returns canned segments
  regardless of input, so the surrounding pipeline can be exercised
  without paying Whisper's startup time or pulling its (large) model
  weights.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from app.agents.contracts import TranscriptSegment
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger

log = get_logger("pipeline.transcriber")


class Transcriber(Protocol):
    """Transcriber interface every implementation conforms to."""

    async def transcribe(
        self, path: Path, *, language: str | None = None
    ) -> list[TranscriptSegment]:
        """Transcribe ``path`` into a list of :class:`TranscriptSegment`.

        ``language`` is a hint (ISO 639-1, e.g. ``"he"``); when
        ``None`` the implementation auto-detects.

        Implementations raise :class:`ExternalServiceError` on any
        failure (model load, decoding, file missing).
        """


class StubTranscriber(Transcriber):
    """Static :class:`Transcriber` for tests and dev environments.

    Returns the supplied segments regardless of input. Constructor
    arguments make the canned output explicit per test.
    """

    def __init__(
        self,
        *,
        segments: Iterable[TranscriptSegment] | None = None,
    ) -> None:
        self._segments: list[TranscriptSegment] = list(segments or [])

    async def transcribe(
        self, path: Path, *, language: str | None = None
    ) -> list[TranscriptSegment]:
        return list(self._segments)


class WhisperTranscriber(Transcriber):
    """Production :class:`Transcriber` driven by ``openai-whisper``.

    The model is loaded lazily on first use and reused for every
    subsequent call. ``model_name`` follows Whisper's naming -
    ``"tiny"`` / ``"base"`` / ``"small"`` / ``"medium"`` / ``"large"``
    or any of the ``"*-v2"`` / ``"*-v3"`` variants. Default is
    ``"small"`` which is the cheapest model that produces usable
    Hebrew transcripts on a CPU.
    """

    def __init__(
        self,
        *,
        model_name: str = "small",
        default_language: str | None = "he",
    ) -> None:
        self._model_name = model_name
        self._default_language = default_language
        self._lock = threading.Lock()
        self._model: Any | None = None

    async def transcribe(
        self, path: Path, *, language: str | None = None
    ) -> list[TranscriptSegment]:
        if not path.exists():
            raise ExternalServiceError(f"asset path does not exist: {path}")
        chosen_language = language or self._default_language
        try:
            return await asyncio.to_thread(self._transcribe_blocking, str(path), chosen_language)
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError(f"whisper failed: {exc}") from exc

    # --- blocking impl --------------------------------------------------

    def _transcribe_blocking(self, path: str, language: str | None) -> list[TranscriptSegment]:
        model = self._ensure_model()
        result = model.transcribe(
            path,
            language=language,
            fp16=False,  # CPU-friendly default; GPU users override
            verbose=False,
        )
        segments: list[TranscriptSegment] = []
        for raw in result.get("segments") or []:
            text = (raw.get("text") or "").strip()
            if not text:
                continue
            start = float(raw.get("start", 0.0))
            end = float(raw.get("end", start))
            if end <= start:
                # Whisper occasionally emits zero-length segments at
                # the very end; skip them so :class:`TranscriptSegment`
                # validation does not reject the whole transcript.
                continue
            segments.append(
                TranscriptSegment(
                    start_seconds=start,
                    end_seconds=end,
                    text=text,
                    language=language or result.get("language") or "he",
                )
            )
        return segments

    def _ensure_model(self) -> Any:
        # Whisper's ``load_model`` is import-heavy and must run
        # exactly once per process. The lock is plain ``threading``
        # because we are inside the worker thread spawned by
        # :func:`asyncio.to_thread`.
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                import whisper

                log.info("whisper.load_model", model_name=self._model_name)
                self._model = whisper.load_model(self._model_name)
        return self._model
