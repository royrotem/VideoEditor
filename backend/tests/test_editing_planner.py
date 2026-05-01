"""Tests for :class:`app.agents.editing_planner.EditingPlanner`."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.agents.client import LLMClient, LLMMessage, LLMResponse
from app.agents.contracts import (
    AssetFacts,
    AudioPlan,
    BriefPlan,
    ClipReference,
    EditDecisionList,
    OutputSpec,
    TimelineClip,
    Track,
)
from app.agents.editing_planner import EditingPlanner, PlannerInput
from app.agents.registry import get_registry


class _ScriptedLLM(LLMClient):
    """LLM that records calls and returns canned replies."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.last_call: dict[str, object] | None = None

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 16000,
        cache_system_prompt: bool = True,
    ) -> LLMResponse:
        self.last_call = {
            "model": model,
            "system_prompt": system_prompt,
            "messages": list(messages),
        }
        return LLMResponse(text=self.replies.pop(0))


def _valid_edl_json(asset_id: str, version: int = 1) -> str:
    """Return a JSON string that matches the EditDecisionList schema."""
    return json.dumps(
        {
            "version": version,
            "timeline": [
                {
                    "kind": "video",
                    "clips": [
                        {
                            "clip": {
                                "asset_id": asset_id,
                                "source_start_seconds": 0.0,
                                "source_end_seconds": 5.0,
                            },
                            "timeline_start_seconds": 0.0,
                            "transition_in": "fade",
                            "transition_out": "cut",
                        }
                    ],
                }
            ],
            "audio": {
                "music_url": None,
                "voice_over_asset_id": None,
                "duck_music_under_voice": True,
                "target_lufs": -14.0,
            },
            "subtitles": None,
            "color": None,
            "output": {
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "container": "mp4",
            },
        }
    )


@pytest.fixture
def asset_facts() -> list[AssetFacts]:
    return [AssetFacts(asset_id=uuid4(), duration_seconds=30.0)]


@pytest.fixture
def brief() -> BriefPlan:
    return BriefPlan(
        title="חתונה — קאט קצר",
        intent="סיכום אנרגטי של 30 שניות",
        target_duration_seconds=30,
        pacing="fast",
    )


async def test_planner_produces_valid_edl(
    asset_facts: list[AssetFacts], brief: BriefPlan
) -> None:
    asset_id = str(asset_facts[0].asset_id)
    llm = _ScriptedLLM([_valid_edl_json(asset_id, version=1)])
    planner = EditingPlanner(llm)

    edl = await planner.run(PlannerInput(brief=brief, asset_facts=asset_facts))

    assert isinstance(edl, EditDecisionList)
    assert edl.version == 1
    assert len(edl.timeline) == 1
    assert edl.timeline[0].clips[0].transition_in == "fade"
    assert str(edl.timeline[0].clips[0].clip.asset_id) == asset_id


async def test_planner_uses_sonnet_4_6(
    asset_facts: list[AssetFacts], brief: BriefPlan
) -> None:
    llm = _ScriptedLLM([_valid_edl_json(str(asset_facts[0].asset_id))])
    planner = EditingPlanner(llm)

    await planner.run(PlannerInput(brief=brief, asset_facts=asset_facts))

    assert llm.last_call is not None
    assert llm.last_call["model"] == "claude-sonnet-4-6"


async def test_planner_input_carries_previous_edl_for_revision(
    asset_facts: list[AssetFacts], brief: BriefPlan
) -> None:
    asset_id = str(asset_facts[0].asset_id)
    llm = _ScriptedLLM([_valid_edl_json(asset_id, version=2)])
    planner = EditingPlanner(llm)

    previous = EditDecisionList(
        version=1,
        timeline=[
            Track(
                kind="video",
                clips=[
                    TimelineClip(
                        clip=ClipReference(
                            asset_id=asset_facts[0].asset_id,
                            source_start_seconds=0,
                            source_end_seconds=10,
                        ),
                        timeline_start_seconds=0,
                    )
                ],
            )
        ],
        audio=AudioPlan(),
        output=OutputSpec(),
    )

    edl = await planner.run(
        PlannerInput(brief=brief, asset_facts=asset_facts, previous_edl=previous)
    )

    assert edl.version == 2
    assert llm.last_call is not None
    body = llm.last_call["messages"][0].content  # type: ignore[index]
    assert "previous_edl" in body
    assert '"version": 1' in body


async def test_planner_registered_in_global_registry() -> None:
    import app.agents  # noqa: F401 - triggers registration

    assert "editing_planner" in get_registry().names()
