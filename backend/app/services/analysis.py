"""Asset analysis use case.

Pulls one asset's bytes onto local disk, runs a :class:`Probe` over it
(``ffprobe`` for duration / resolution / audio presence), optionally
transcribes the audio via :class:`Transcriber` (Whisper), then -
when wired in - extracts a handful of sample frames and asks the
Vision Analyzer agent for a Hebrew summary plus per-shot
descriptions. Persists everything into ``assets.analysis`` and
flips ``status``.

Lives in ``services`` rather than in ``pipeline`` because it is the
orchestration layer - it owns the DB and storage interactions. The
probe, transcriber, frame extractor, and the agent themselves stay
pure functions of their inputs.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Literal, cast
from uuid import UUID

from app.agents.client import ImageBlock, LLMClient
from app.agents.contracts import TranscriptSegment
from app.agents.vision_analyzer import (
    VisionAnalysisInput,
    VisionAnalysisOutput,
    VisionAnalyzer,
)
from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.enums import AssetStatus
from app.db.models import Asset
from app.pipeline.frame_extractor import ExtractedFrame, FrameExtractor
from app.pipeline.probe import Probe, ProbeResult
from app.pipeline.transcriber import Transcriber
from app.repositories.assets import AssetRepository
from app.storage.base import ObjectStore

DEFAULT_VISION_FRAME_COUNT = 6


class AssetAnalysisService:
    """Runs the deterministic + qualitative analysis stages on one asset."""

    def __init__(
        self,
        *,
        probe: Probe,
        object_store: ObjectStore,
        assets: AssetRepository,
        frame_extractor: FrameExtractor | None = None,
        llm: LLMClient | None = None,
        transcriber: Transcriber | None = None,
        vision_frame_count: int = DEFAULT_VISION_FRAME_COUNT,
    ) -> None:
        self._probe = probe
        self._object_store = object_store
        self._assets = assets
        self._frame_extractor = frame_extractor
        self._llm = llm
        self._transcriber = transcriber
        self._vision_frame_count = vision_frame_count
        self._log = get_logger("services.analysis")

    async def analyze(self, asset_id: UUID) -> Asset:
        """Probe ``asset_id``, optionally transcribe + run vision, persist.

        The probe is mandatory; transcription and vision are
        best-effort. If a dependency is not configured, or if a step
        raises, the asset still ends up in ``status=ready`` with the
        probe facts populated. Failed best-effort steps are logged as
        warnings, not propagated.
        """
        asset = await self._assets.get(asset_id)
        asset.status = AssetStatus.ANALYZING

        scratch = Path(tempfile.mkdtemp(prefix="probe-"))
        try:
            local_path = scratch / Path(asset.filename).name
            data = await self._object_store.get(asset.s3_bucket, asset.s3_key)
            local_path.write_bytes(data)

            try:
                probe_result = await self._probe.probe(local_path)
            except AppError as exc:
                self._log.warning(
                    "analysis.probe_failed",
                    asset_id=str(asset.id),
                    error=exc.message,
                )
                asset.status = AssetStatus.FAILED
                asset.analysis = {"error": exc.message}
                return asset

            asset.analysis = _merge_probe_into_analysis(asset.analysis, probe_result)

            await self._maybe_transcribe(asset, local_path, probe_result)
            await self._maybe_run_vision_pass(asset, local_path, probe_result)

            asset.status = AssetStatus.READY
            self._log.info(
                "analysis.complete",
                asset_id=str(asset.id),
                duration_seconds=probe_result.duration_seconds,
                has_transcript=bool((asset.analysis or {}).get("transcript")),
                has_summary=bool((asset.analysis or {}).get("summary")),
            )
            return asset
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    async def _maybe_transcribe(
        self,
        asset: Asset,
        local_path: Path,
        probe_result: ProbeResult,
    ) -> None:
        """Best-effort Whisper pass.

        Skipped silently when:

        - the transcriber is not configured (e.g. tests / dev without
          ``openai-whisper`` weights),
        - the probe reports no audio track,
        - the probe reports zero duration,
        - the call raises - logged as a warning; the deterministic
          half of the analysis is still stored.
        """
        if (
            self._transcriber is None
            or not probe_result.has_audio
            or probe_result.duration_seconds <= 0
        ):
            return

        try:
            segments = await self._transcriber.transcribe(local_path)
        except AppError as exc:
            self._log.warning(
                "analysis.transcribe_failed",
                asset_id=str(asset.id),
                error=exc.message,
            )
            return

        asset.analysis = _merge_transcript_into_analysis(asset.analysis, segments)

    async def _maybe_run_vision_pass(
        self,
        asset: Asset,
        local_path: Path,
        probe_result: ProbeResult,
    ) -> None:
        """Best-effort vision pass: extract frames + run the agent.

        Skipped silently when:

        - the frame extractor or LLM client is not configured (e.g.
          tests without vision deps),
        - the probe reports zero duration (no frames to extract),
        - any step raises - logged as a warning, but the deterministic
          half of the analysis is still stored.
        """
        if self._frame_extractor is None or self._llm is None or probe_result.duration_seconds <= 0:
            return

        try:
            frames = await self._frame_extractor.extract(
                local_path,
                count=self._vision_frame_count,
                duration_seconds=probe_result.duration_seconds,
            )
        except AppError as exc:
            self._log.warning(
                "analysis.frame_extract_failed",
                asset_id=str(asset.id),
                error=exc.message,
            )
            return

        try:
            output = await self._run_vision_agent(asset.id, probe_result, frames)
        except AppError as exc:
            self._log.warning(
                "analysis.vision_agent_failed",
                asset_id=str(asset.id),
                error=exc.message,
            )
            return

        asset.analysis = _merge_vision_into_analysis(asset.analysis, output)

    async def _run_vision_agent(
        self,
        asset_id: UUID,
        probe_result: ProbeResult,
        frames: list[ExtractedFrame],
    ) -> VisionAnalysisOutput:
        assert self._llm is not None  # narrowed by the caller
        agent_input = VisionAnalysisInput(
            asset_id=asset_id,
            duration_seconds=probe_result.duration_seconds,
            width=probe_result.width,
            height=probe_result.height,
            has_audio=probe_result.has_audio,
        )
        image_blocks = [
            ImageBlock(data=f.data, media_type=_to_anthropic_media_type(f.media_type))
            for f in frames
        ]
        return await VisionAnalyzer(self._llm).run_with_frames(agent_input, image_blocks)


def _merge_probe_into_analysis(
    existing: dict[str, object] | None, result: ProbeResult
) -> dict[str, object]:
    """Layer probe facts on top of any prior analysis.

    Future stages (Whisper transcription, deeper scene detection)
    will write to additional keys of the same ``analysis`` blob.
    Keeping a merge step here means re-running the probe alone does
    not blow away those richer fields.
    """
    merged: dict[str, object] = dict(existing or {})
    merged.update(
        {
            "duration_seconds": result.duration_seconds,
            "width": result.width,
            "height": result.height,
            "has_audio": result.has_audio,
            "container_format": result.container_format,
        }
    )
    return merged


def _merge_vision_into_analysis(
    existing: dict[str, object] | None, output: VisionAnalysisOutput
) -> dict[str, object]:
    """Layer vision-agent facts on top of the probe-stage analysis."""
    merged: dict[str, object] = dict(existing or {})
    merged["summary"] = output.summary
    merged["shots"] = [shot.model_dump(mode="json") for shot in output.shots]
    return merged


def _merge_transcript_into_analysis(
    existing: dict[str, object] | None, segments: list[TranscriptSegment]
) -> dict[str, object]:
    """Layer Whisper segments on top of the probe-stage analysis."""
    merged: dict[str, object] = dict(existing or {})
    merged["transcript"] = [s.model_dump(mode="json") for s in segments]
    return merged


_AnthropicImageMediaType = Literal["image/jpeg", "image/png", "image/gif", "image/webp"]


def _to_anthropic_media_type(media_type: str) -> _AnthropicImageMediaType:
    """Coerce common media types to the literal Anthropic expects.

    The API accepts ``image/jpeg``, ``image/png``, ``image/gif``,
    ``image/webp``. Anything else from the extractor falls back to
    ``image/jpeg`` since that is what FFmpegFrameExtractor produces.
    """
    if media_type in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
        return cast(_AnthropicImageMediaType, media_type)
    return "image/jpeg"
