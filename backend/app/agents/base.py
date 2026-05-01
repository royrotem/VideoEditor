"""Base classes every Claude agent inherits from.

Two flavours:

- :class:`Agent` - a single-shot agent. Takes one Pydantic input model,
  returns one Pydantic output model. The Editing Planner, Vision
  Analyzer, and QA Reviewer are agents of this kind.
- :class:`ChatAgent` - a multi-turn conversational agent. The Creative
  Director is the only one of these.

Both share the same plumbing: a system prompt, a model name, an
:class:`LLMClient` they delegate to, and a name used in logs and
:mod:`app.db.models.Message.agent_name`.
"""

from __future__ import annotations

import json
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.agents.client import LLMClient, LLMMessage, LLMResponse
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

AgentInput = BaseModel
AgentOutput = BaseModel


class Agent(Generic[InputT, OutputT]):
    """Single-shot Claude agent: one input model in, one output model out.

    Subclasses set :attr:`system_prompt`, :attr:`model`, :attr:`name`,
    and :attr:`output_model`, then call :meth:`run` with a typed input.
    The base class formats the user message, talks to the LLM, parses
    the reply as the declared output model, and returns it.

    The on-the-wire convention is JSON: agents are instructed (in their
    system prompt) to return a single JSON object that matches their
    output schema. This keeps the inter-agent vocabulary deterministic
    and makes failures easy to detect.
    """

    name: str = "agent"
    model: str = ""
    system_prompt: str = ""
    output_model: type[OutputT]

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self._log = get_logger(f"agents.{self.name}")

    async def run(self, input_payload: InputT) -> OutputT:
        """Execute one agent turn against ``input_payload``."""
        if not self.system_prompt or not self.model:
            raise NotImplementedError(
                f"agent {type(self).__name__} must set system_prompt and model"
            )

        user_message = self._format_user_message(input_payload)
        self._log.info("agent.run.start", model=self.model)

        response = await self._llm.complete(
            model=self.model,
            system_prompt=self.system_prompt,
            messages=[LLMMessage(role="user", content=user_message)],
        )
        self._log.info(
            "agent.run.complete",
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cache_read=response.cache_read_input_tokens,
        )

        return self._parse_output(response)

    def _format_user_message(self, input_payload: InputT) -> str:
        """Default: serialise the input model as a JSON object.

        Override to inject extra context (style guide, examples, etc.).
        """
        return input_payload.model_dump_json(indent=2)

    def _parse_output(self, response: LLMResponse) -> OutputT:
        """Parse ``response.text`` as :attr:`output_model`.

        Tolerates the common "I'll return JSON inside a code fence" reply
        by stripping triple-backtick fences. Raises
        :class:`ExternalServiceError` if the LLM returned something we
        cannot parse - this lets callers surface a stable error type.
        """
        cleaned = _strip_code_fence(response.text)
        try:
            data = json.loads(cleaned)
            return self.output_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            self._log.warning("agent.output.invalid", text=response.text[:500])
            raise ExternalServiceError(f"agent {self.name} returned invalid output: {exc}") from exc


class ChatAgent:
    """Multi-turn Claude agent that holds a Hebrew dialogue with the user.

    Unlike :class:`Agent`, the output is free-form Hebrew text - the
    Creative Director chats until the user approves a plan, at which
    point a separate :class:`Agent` (the Editing Planner) extracts a
    structured :class:`~app.agents.contracts.BriefPlan`.
    """

    name: str = "chat_agent"
    model: str = ""
    system_prompt: str = ""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self._log = get_logger(f"agents.{self.name}")

    async def reply(self, history: list[LLMMessage]) -> str:
        """Produce the next assistant turn given the prior conversation."""
        if not self.system_prompt or not self.model:
            raise NotImplementedError(
                f"chat agent {type(self).__name__} must set system_prompt and model"
            )

        response = await self._llm.complete(
            model=self.model,
            system_prompt=self.system_prompt,
            messages=history,
        )
        self._log.info(
            "chat_agent.reply",
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
        return response.text


def _strip_code_fence(text: str) -> str:
    """Remove a leading ```json / ``` fence if the model wrapped its reply."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    # Drop the opening fence line and the trailing fence.
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
