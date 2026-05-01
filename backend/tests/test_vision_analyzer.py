"""Tests for the Vision Analyzer agent + image-aware LLMClient bits."""

from __future__ import annotations

import base64
import json
from uuid import uuid4

import pytest

from app.agents.client import ImageBlock, LLMClient, LLMMessage, LLMResponse
from app.agents.client import _render_message
from app.agents.contracts import AssetFacts
from app.agents.registry import get_registry
from app.agents.vision_analyzer import (
    VisionAnalysisInput,
    VisionAnalysisOutput,
    VisionAnalyzer,
    merge_into_asset_facts,
)
from app.core.errors import ExternalServiceError


class _RecordingLLM(LLMClient):
    """LLM fake that captures every call and returns canned replies."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.last_messages: list[LLMMessage] | None = None

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 16000,
        cache_system_prompt: bool = True,
    ) -> LLMResponse:
        self.last_messages = list(messages)
        return LLMResponse(text=self.replies.pop(0))


# --- LLMClient image rendering ------------------------------------------


def test_render_message_keeps_plain_text_form_when_no_images() -> None:
    rendered = _render_message(LLMMessage(role="user", content="היי"))

    assert rendered == {"role": "user", "content": "היי"}


def test_render_message_emits_image_blocks_then_text_when_images_present() -> None:
    image_bytes = b"\x89PNG\r\n\x1a\n"  # arbitrary bytes
    rendered = _render_message(
        LLMMessage(
            role="user",
            content="describe the frames",
            images=[ImageBlock(data=image_bytes, media_type="image/png")],
        )
    )

    assert rendered["role"] == "user"
    blocks = rendered["content"]
    assert isinstance(blocks, list)
    assert blocks[0] == {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.b64encode(image_bytes).decode("ascii"),
        },
    }
    assert blocks[1] == {"type": "text", "text": "describe the frames"}


# --- Vision Analyzer ----------------------------------------------------


def _valid_output_json() -> str:
    return json.dumps(
        {
            "summary": "סרטון רחוב כהה עם תאורת רחוב חמה.",
            "shots": [
                {
                    "start_seconds": 0,
                    "end_seconds": 3,
                    "description": "רחוב סואן בלילה",
                    "dominant_colors": ["שחור", "כתום"],
                    "motion_intensity": 0.4,
                },
                {
                    "start_seconds": 3,
                    "end_seconds": 6,
                    "description": "רכב חולף",
                    "dominant_colors": ["אדום", "שחור"],
                    "motion_intensity": 0.8,
                },
            ],
        }
    )


@pytest.fixture
def base_input() -> VisionAnalysisInput:
    return VisionAnalysisInput(
        asset_id=uuid4(),
        duration_seconds=6.0,
        width=1920,
        height=1080,
        has_audio=True,
    )


async def test_run_with_frames_attaches_images_to_user_message(
    base_input: VisionAnalysisInput,
) -> None:
    llm = _RecordingLLM([_valid_output_json()])
    agent = VisionAnalyzer(llm)

    frames = [
        ImageBlock(data=b"frame-0", media_type="image/jpeg"),
        ImageBlock(data=b"frame-1", media_type="image/jpeg"),
    ]
    await agent.run_with_frames(base_input, frames)

    assert llm.last_messages is not None
    assert len(llm.last_messages) == 1
    sent = llm.last_messages[0]
    assert sent.role == "user"
    assert sent.images == frames
    assert "ASSET_FACTS:" in sent.content
    assert f"asset_id: {base_input.asset_id}" in sent.content


async def test_run_with_frames_parses_valid_output(
    base_input: VisionAnalysisInput,
) -> None:
    llm = _RecordingLLM([_valid_output_json()])
    agent = VisionAnalyzer(llm)

    output = await agent.run_with_frames(base_input, [])

    assert isinstance(output, VisionAnalysisOutput)
    assert output.summary.startswith("סרטון")
    assert len(output.shots) == 2
    assert output.shots[1].motion_intensity == pytest.approx(0.8)


async def test_run_without_frames_still_works(
    base_input: VisionAnalysisInput,
) -> None:
    """Frames are optional — the deterministic-only path is supported."""
    llm = _RecordingLLM([_valid_output_json()])
    agent = VisionAnalyzer(llm)

    output = await agent.run_with_frames(base_input, [])

    assert llm.last_messages is not None
    assert llm.last_messages[0].images == []
    assert isinstance(output, VisionAnalysisOutput)


async def test_run_with_frames_rejects_non_json_reply(
    base_input: VisionAnalysisInput,
) -> None:
    llm = _RecordingLLM(["I think the video is..."])
    agent = VisionAnalyzer(llm)

    with pytest.raises(ExternalServiceError):
        await agent.run_with_frames(base_input, [])


def test_merge_into_asset_facts_composes_deterministic_and_qualitative(
    base_input: VisionAnalysisInput,
) -> None:
    qualitative = VisionAnalysisOutput(
        summary="סיכום",
        shots=[
            {
                "start_seconds": 0,
                "end_seconds": 6,
                "description": "כל הסרטון",
                "dominant_colors": [],
                "motion_intensity": 0.2,
            },
        ],  # type: ignore[list-item]
    )

    facts = merge_into_asset_facts(base=base_input, output=qualitative)

    assert isinstance(facts, AssetFacts)
    assert facts.asset_id == base_input.asset_id
    assert facts.duration_seconds == base_input.duration_seconds
    assert facts.width == base_input.width
    assert facts.height == base_input.height
    assert facts.has_audio is True
    assert facts.summary == "סיכום"
    assert len(facts.shots) == 1


# --- Registry wiring ----------------------------------------------------


def test_vision_analyzer_registered_in_global_registry() -> None:
    import app.agents  # noqa: F401 - triggers registration

    assert "vision_analyzer" in get_registry().names()
