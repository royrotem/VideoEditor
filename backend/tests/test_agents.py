"""Unit tests for the agent framework.

The tests inject a fake :class:`LLMClient` so they do not touch the
network. Production agents will plug into the same plumbing.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.agents.base import Agent, ChatAgent
from app.agents.client import LLMClient, LLMMessage, LLMResponse
from app.agents.registry import AgentRegistry
from app.core.errors import ExternalServiceError, NotFoundError


class _FakeLLM(LLMClient):
    """Records calls and returns canned replies."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, object]] = []

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 16000,
        cache_system_prompt: bool = True,
    ) -> LLMResponse:
        self.calls.append(
            {
                "model": model,
                "system_prompt": system_prompt,
                "messages": [(m.role, m.content) for m in messages],
            }
        )
        text = self.replies.pop(0)
        return LLMResponse(text=text, input_tokens=10, output_tokens=20)


# --- Single-shot Agent ---------------------------------------------------


class _Greeting(BaseModel):
    name: str


class _Reply(BaseModel):
    salutation: str
    formal: bool


class _GreetingAgent(Agent[_Greeting, _Reply]):
    name = "greeting_test_agent"
    model = "claude-haiku-4-5-20251001"
    system_prompt = "Reply with JSON {salutation, formal}."
    output_model = _Reply


async def test_agent_returns_parsed_output_model() -> None:
    llm = _FakeLLM(['{"salutation": "שלום", "formal": false}'])
    agent = _GreetingAgent(llm)

    result = await agent.run(_Greeting(name="רועי"))

    assert result.salutation == "שלום"
    assert result.formal is False
    assert llm.calls[0]["model"] == "claude-haiku-4-5-20251001"


async def test_agent_strips_markdown_code_fence() -> None:
    llm = _FakeLLM(['```json\n{"salutation": "hi", "formal": true}\n```'])
    agent = _GreetingAgent(llm)

    result = await agent.run(_Greeting(name="x"))
    assert result.formal is True


async def test_agent_raises_external_service_error_on_invalid_json() -> None:
    llm = _FakeLLM(["definitely not json"])
    agent = _GreetingAgent(llm)

    with pytest.raises(ExternalServiceError):
        await agent.run(_Greeting(name="x"))


async def test_agent_raises_external_service_error_on_schema_mismatch() -> None:
    llm = _FakeLLM(['{"unexpected": 1}'])
    agent = _GreetingAgent(llm)

    with pytest.raises(ExternalServiceError):
        await agent.run(_Greeting(name="x"))


async def test_agent_without_system_prompt_raises() -> None:
    class _Broken(Agent[_Greeting, _Reply]):
        name = "broken_agent"
        output_model = _Reply
        # missing model + system_prompt

    with pytest.raises(NotImplementedError):
        await _Broken(_FakeLLM([])).run(_Greeting(name="x"))


# --- ChatAgent -----------------------------------------------------------


class _ChattyAgent(ChatAgent):
    name = "chatty_test_agent"
    model = "claude-opus-4-7"
    system_prompt = "אתה במאי יצירתי. ענה בעברית."


async def test_chat_agent_returns_assistant_text() -> None:
    llm = _FakeLLM(["אהבתי את הרעיון!"])
    agent = _ChattyAgent(llm)

    reply = await agent.reply([LLMMessage(role="user", content="היי")])

    assert reply == "אהבתי את הרעיון!"
    assert llm.calls[0]["messages"] == [("user", "היי")]


# --- AgentRegistry -------------------------------------------------------


def test_registry_round_trips_an_agent_class() -> None:
    registry = AgentRegistry()
    registry.register(_GreetingAgent)

    built = registry.build("greeting_test_agent", _FakeLLM([]))

    assert isinstance(built, _GreetingAgent)
    assert registry.names() == ["greeting_test_agent"]


def test_registry_rejects_duplicate_names() -> None:
    registry = AgentRegistry()
    registry.register(_GreetingAgent)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(_GreetingAgent)


def test_registry_rejects_default_class_names() -> None:
    class _NoName(Agent[_Greeting, _Reply]):
        # leaves the default `name = "agent"`
        output_model = _Reply
        model = "x"
        system_prompt = "y"

    with pytest.raises(ValueError, match="must declare a unique 'name'"):
        AgentRegistry().register(_NoName)


def test_registry_raises_not_found_for_unknown_agent() -> None:
    with pytest.raises(NotFoundError):
        AgentRegistry().build("does_not_exist", _FakeLLM([]))
