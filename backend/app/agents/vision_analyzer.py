"""Vision Analyzer - turn deterministic probe facts + sample frames
into qualitative AssetFacts (summary + per-shot descriptions).

This agent is the first one in the network that uses Claude's vision
capability. The deterministic facts (duration, resolution,
``has_audio``) come from the FFprobe stage; the sample frames are
extracted by a future :class:`FrameExtractor`. The agent only
contributes the qualitative bits - asset id and the deterministic
facts pass through unchanged so the output is a complete
:class:`AssetFacts` ready to be merged into ``asset.analysis``.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.agents.client import ImageBlock, LLMMessage
from app.agents.contracts import AssetFacts, Shot
from app.agents.prompts.vision_analyzer import VISION_ANALYZER_SYSTEM_PROMPT
from app.agents.registry import get_registry


class VisionAnalysisInput(BaseModel):
    """Everything the Vision Analyzer needs to do its work.

    The frames live outside Pydantic because they are bytes (not JSON-
    friendly); the agent's :meth:`_build_messages` overrides reach for
    them through the ``frames`` attribute on this model. Pydantic's
    ``arbitrary_types_allowed`` would let us declare them as a field,
    but keeping them out of the model means Pydantic serialisation
    (used by the base :class:`Agent` to render the user message)
    leaves them to the agent-specific code.
    """

    asset_id: UUID
    duration_seconds: float = Field(ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    has_audio: bool = False


class VisionAnalysisOutput(BaseModel):
    """Qualitative facts the agent contributes.

    The orchestration layer composes this with the deterministic
    fields to build a full :class:`AssetFacts`.
    """

    summary: str
    shots: list[Shot]


@get_registry().register
class VisionAnalyzer(Agent[VisionAnalysisInput, VisionAnalysisOutput]):
    """Single-shot vision-capable agent.

    Override :meth:`run` (rather than only ``_format_user_message``)
    so we can attach :class:`ImageBlock` instances to the user turn.
    """

    name = "vision_analyzer"
    model = "claude-sonnet-4-6"
    system_prompt = VISION_ANALYZER_SYSTEM_PROMPT
    output_model = VisionAnalysisOutput

    async def run_with_frames(
        self,
        input_payload: VisionAnalysisInput,
        frames: list[ImageBlock],
    ) -> VisionAnalysisOutput:
        """Vision-aware variant of :meth:`Agent.run`.

        We keep :meth:`Agent.run` working too (frames default to
        empty), so callers that already have a deterministic-only
        analysis path can use the agent without changes.
        """
        user_text = self._format_user_message(input_payload)
        message = LLMMessage(role="user", content=user_text, images=frames)

        response = await self._llm.complete(
            model=self.model,
            system_prompt=self.system_prompt,
            messages=[message],
        )
        return self._parse_output(response)

    def _format_user_message(self, input_payload: VisionAnalysisInput) -> str:
        """Render the deterministic facts as a labeled block.

        The frames themselves are attached as image content blocks
        (see :meth:`run_with_frames`); the text references them by
        index so the model can correlate timestamps to images.
        """
        return (
            "ASSET_FACTS:\n"
            f"  asset_id: {input_payload.asset_id}\n"
            f"  duration_seconds: {input_payload.duration_seconds:.3f}\n"
            f"  width: {input_payload.width}\n"
            f"  height: {input_payload.height}\n"
            f"  has_audio: {input_payload.has_audio}\n\n"
            "התמונות המצורפות הן דגימות שצולמו במרווחים שווים מהווידאו "
            "(הראשונה ב-0s, האחרונה קרוב ל-duration_seconds).\n\n"
            "החזר/י כעת את אובייקט ה-JSON היחיד שמתאר את הסיכום והסצנות."
        )


def merge_into_asset_facts(
    *, base: VisionAnalysisInput, output: VisionAnalysisOutput
) -> AssetFacts:
    """Compose the deterministic and qualitative halves into one model.

    Lives next to the agent so callers don't have to know which
    fields came from which side.
    """
    return AssetFacts(
        asset_id=base.asset_id,
        duration_seconds=base.duration_seconds,
        width=base.width,
        height=base.height,
        has_audio=base.has_audio,
        shots=output.shots,
        summary=output.summary,
    )
