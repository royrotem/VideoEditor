"""Brief Extractor - turn an approved Creative-Director chat into a BriefPlan.

Runs once, after :func:`creative_director.is_approval_message` matches
on the Director's last message. Reads the entire conversation as a
plain transcript and emits a structured
:class:`~app.agents.contracts.BriefPlan`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.agents.client import LLMMessage
from app.agents.contracts import BriefPlan
from app.agents.prompts.brief_extractor import BRIEF_EXTRACTOR_SYSTEM_PROMPT
from app.agents.registry import get_registry


class LLMMessageDict(BaseModel):
    """Pydantic mirror of :class:`LLMMessage` so the input is a model."""

    role: str
    content: str


class ConversationTranscript(BaseModel):
    """Input model for :class:`BriefExtractor`.

    A flat list of role/content turns is enough - the extractor does
    not need the original timestamps or message ids.
    """

    turns: list[LLMMessageDict] = Field(default_factory=list)

    @classmethod
    def from_messages(cls, messages: list[LLMMessage]) -> "ConversationTranscript":
        return cls(
            turns=[LLMMessageDict(role=m.role, content=m.content) for m in messages]
        )


@get_registry().register
class BriefExtractor(Agent[ConversationTranscript, BriefPlan]):
    """Single-shot agent that extracts a :class:`BriefPlan` from a chat."""

    name = "brief_extractor"
    model = "claude-sonnet-4-6"
    system_prompt = BRIEF_EXTRACTOR_SYSTEM_PROMPT
    output_model = BriefPlan

    def _format_user_message(self, input_payload: ConversationTranscript) -> str:
        """Render the conversation as a labeled transcript.

        Using a plain transcript (rather than a JSON dump) keeps the
        prompt small and human-readable in logs, and matches what the
        system prompt asks the model to read.
        """
        if not input_payload.turns:
            return "תמליל ריק. החזר/י BriefPlan עם ערכי ברירת מחדל לפי הסכמה."
        lines: list[str] = ["TRANSCRIPT:"]
        for turn in input_payload.turns:
            speaker = "משתמש" if turn.role == "user" else "במאי"
            lines.append(f"[{speaker}] {turn.content}")
        lines.append(
            "\nהחזר/י כעת את אובייקט ה-JSON היחיד שמתאר את ה-BriefPlan."
        )
        return "\n".join(lines)
