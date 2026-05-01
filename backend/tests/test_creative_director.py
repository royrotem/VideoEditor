"""Tests for the Creative Director chat agent and Brief Extractor."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agents.brief_extractor import (
    BriefExtractor,
    ConversationTranscript,
    LLMMessageDict,
)
from app.agents.client import LLMClient, LLMMessage, LLMResponse
from app.agents.contracts import AssetFacts, BriefPlan
from app.agents.creative_director import (
    APPROVAL_MARKER,
    CreativeDirector,
    is_approval_message,
)
from app.agents.registry import get_registry
from app.core.errors import ExternalServiceError


class _RecordingLLM(LLMClient):
    """Captures the last call and returns the next queued reply."""

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


# --- Creative Director ---------------------------------------------------


async def test_creative_director_opening_message_includes_brief_and_facts() -> None:
    facts = [AssetFacts(asset_id=uuid4(), duration_seconds=42.0)]

    opening = CreativeDirector.build_opening_user_message(
        brief="סרטון קצר על החתונה של אחותי", asset_facts=facts
    )

    assert opening.role == "user"
    assert "BRIEF:" in opening.content
    assert "ASSET_FACTS:" in opening.content
    assert "אחותי" in opening.content
    assert str(facts[0].asset_id) in opening.content


async def test_creative_director_opening_message_handles_no_assets() -> None:
    opening = CreativeDirector.build_opening_user_message(brief="רעיון ראשוני", asset_facts=[])

    assert "ASSET_FACTS:\n[]" in opening.content


async def test_creative_director_reply_uses_opus_4_7() -> None:
    llm = _RecordingLLM(["יש לי שתי הצעות..."])
    agent = CreativeDirector(llm)

    reply = await agent.reply([LLMMessage(role="user", content="היי, רוצה משהו קצר ואנרגטי")])

    assert reply == "יש לי שתי הצעות..."
    assert llm.last_call is not None
    assert llm.last_call["model"] == "claude-opus-4-7"


def test_is_approval_message_detects_summary_marker() -> None:
    assert is_approval_message(f"{APPROVAL_MARKER} סרטון של 30 שניות, אנרגטי...")
    assert is_approval_message(f"  \n  {APPROVAL_MARKER} עם רווחים בהתחלה")


def test_is_approval_message_rejects_non_summary_text() -> None:
    assert not is_approval_message("יש לי כיוון: אפשר לעשות סרטון אנרגטי...")
    assert not is_approval_message("מה דעתך על המוזיקה?")
    assert not is_approval_message("")


# --- Brief Extractor -----------------------------------------------------


async def test_brief_extractor_parses_valid_brief_plan() -> None:
    llm = _RecordingLLM(
        [
            '{"title":"חתונה — קאט קצר",'
            '"intent":"סיכום אנרגטי של 30 שניות מהחתונה של אחותי, עם הדגש על רגעי שמחה.",'
            '"target_duration_seconds":30,'
            '"style_notes":["אנרגטי","קצב מהיר"],'
            '"music_direction":"פופ עברי עליז",'
            '"pacing":"fast"}'
        ]
    )
    agent = BriefExtractor(llm)

    transcript = ConversationTranscript(
        turns=[
            LLMMessageDict(role="user", content="רוצה משהו קצר ואנרגטי מהחתונה"),
            LLMMessageDict(role="assistant", content="יש לי שתי הצעות: A. ... B. ..."),
            LLMMessageDict(role="user", content="בוא נלך עם A"),
            LLMMessageDict(
                role="assistant",
                content="סיכום: סרטון אנרגטי של 30 שניות עם פופ עברי עליז.",
            ),
        ]
    )

    plan = await agent.run(transcript)

    assert isinstance(plan, BriefPlan)
    assert plan.title == "חתונה — קאט קצר"
    assert plan.target_duration_seconds == 30
    assert plan.pacing == "fast"
    assert plan.music_direction == "פופ עברי עליז"


async def test_brief_extractor_formats_transcript_with_speakers() -> None:
    llm = _RecordingLLM(
        [
            '{"title":"x","intent":"y","target_duration_seconds":60,'
            '"style_notes":[],"music_direction":null,"pacing":"medium"}'
        ]
    )
    agent = BriefExtractor(llm)
    transcript = ConversationTranscript(
        turns=[
            LLMMessageDict(role="user", content="היי"),
            LLMMessageDict(role="assistant", content="שלום"),
        ]
    )

    await agent.run(transcript)

    assert llm.last_call is not None
    sent_messages = llm.last_call["messages"]
    assert len(sent_messages) == 1  # type: ignore[arg-type]
    body = sent_messages[0].content  # type: ignore[index]
    assert "[משתמש] היי" in body
    assert "[במאי] שלום" in body


async def test_brief_extractor_uses_sonnet_4_6() -> None:
    llm = _RecordingLLM(
        [
            '{"title":"x","intent":"y","target_duration_seconds":60,'
            '"style_notes":[],"music_direction":null,"pacing":"medium"}'
        ]
    )
    agent = BriefExtractor(llm)

    await agent.run(ConversationTranscript(turns=[]))

    assert llm.last_call is not None
    assert llm.last_call["model"] == "claude-sonnet-4-6"


async def test_brief_extractor_rejects_non_json_reply() -> None:
    llm = _RecordingLLM(["אני חושב שהתוכנית היא..."])
    agent = BriefExtractor(llm)

    with pytest.raises(ExternalServiceError):
        await agent.run(ConversationTranscript(turns=[]))


def test_conversation_transcript_from_llm_messages() -> None:
    transcript = ConversationTranscript.from_messages(
        [
            LLMMessage(role="user", content="א"),
            LLMMessage(role="assistant", content="ב"),
        ]
    )
    assert [t.role for t in transcript.turns] == ["user", "assistant"]
    assert [t.content for t in transcript.turns] == ["א", "ב"]


# --- Registry wiring -----------------------------------------------------


def test_both_agents_registered_under_their_names() -> None:
    # Importing app.agents triggers the @register decorators.
    import app.agents  # noqa: F401

    names = get_registry().names()
    assert "creative_director" in names
    assert "brief_extractor" in names
