"""Creative Director - the iterative Hebrew dialogue with the user.

Talks to the user in Hebrew, proposes 2-3 concrete directions per turn
based on the analysed assets, and signals approval by starting its
final reply with the literal token ``"סיכום:"``. The Brief Extractor
agent runs after that to convert the conversation into a structured
:class:`~app.agents.contracts.BriefPlan`.
"""

from __future__ import annotations

from app.agents.base import ChatAgent
from app.agents.client import LLMMessage
from app.agents.contracts import AssetFacts
from app.agents.prompts.creative_director import CREATIVE_DIRECTOR_SYSTEM_PROMPT
from app.agents.registry import get_registry

#: Marker the Creative Director starts its closing message with. The
#: API layer uses this to detect that the conversation has converged
#: and the Brief Extractor can run.
APPROVAL_MARKER = "סיכום:"


@get_registry().register
class CreativeDirector(ChatAgent):
    """Hebrew, multi-turn conversational agent.

    Use :meth:`build_opening_user_message` to format the first user
    turn so it carries the analysed asset facts. Subsequent turns are
    plain user messages and the prior conversation history.
    """

    name = "creative_director"
    model = "claude-opus-4-7"
    system_prompt = CREATIVE_DIRECTOR_SYSTEM_PROMPT

    @staticmethod
    def build_opening_user_message(*, brief: str, asset_facts: list[AssetFacts]) -> LLMMessage:
        """Format the first user turn for a new chat session.

        The asset facts are serialised under an ASSET_FACTS header so
        the prompt's "use only what's there" rule has something to
        clamp on.
        """
        facts_json = "[]"
        if asset_facts:
            facts_json = (
                "[\n" + ",\n".join(fact.model_dump_json(indent=2) for fact in asset_facts) + "\n]"
            )
        body = (
            f"BRIEF:\n{brief}\n\n"
            f"ASSET_FACTS:\n{facts_json}\n\n"
            "ענה/י לפי החוקים בהוראות המערכת."
        )
        return LLMMessage(role="user", content=body)


def is_approval_message(text: str) -> bool:
    """Return whether ``text`` is the Director's closing summary.

    The convention - documented in the system prompt - is that a
    closing message starts with the literal token ``"סיכום:"``.
    """
    return text.lstrip().startswith(APPROVAL_MARKER)
