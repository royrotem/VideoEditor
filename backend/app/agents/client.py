"""LLM client wrapper.

Agents talk to Claude through the :class:`LLMClient` protocol so that:

- the production code path uses the official Anthropic SDK,
- tests inject a fake client that returns canned responses,
- swapping models or providers later is a one-line change.

The default implementation is :class:`AnthropicLLMClient`. It uses
adaptive thinking, prompt caching for the (large, stable) system prompt,
and streams responses to keep request timeouts predictable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from anthropic import AsyncAnthropic

from app.core.errors import ExternalServiceError


@dataclass(slots=True)
class LLMMessage:
    """One turn in a conversation handed to the LLM."""

    role: Literal["user", "assistant"]
    content: str


@dataclass(slots=True)
class LLMResponse:
    """The text result of one LLM call, plus token accounting."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


class LLMClient(Protocol):
    """Minimal LLM interface every agent depends on.

    Two methods on purpose: a one-shot ``complete`` for synchronous
    agent steps, and a streaming variant for long chat turns. Anything
    fancier (tool use, vision) belongs on dedicated subclasses, not on
    this protocol - keep the contract small.
    """

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 16000,
        cache_system_prompt: bool = True,
    ) -> LLMResponse:
        """Run a single completion; return the assistant's text reply."""


class AnthropicLLMClient(LLMClient):
    """Production :class:`LLMClient` backed by the Anthropic SDK.

    The constructor accepts an :class:`AsyncAnthropic` so tests can
    inject a fake transport, and so a single shared client can serve
    every agent in the process (the SDK is connection-pooled).
    """

    def __init__(self, client: AsyncAnthropic) -> None:
        self._client = client

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 16000,
        cache_system_prompt: bool = True,
    ) -> LLMResponse:
        # We cache the (large, stable) system prompt so repeated agent
        # calls within a session reuse the prefix and pay ~0.1x for it.
        system_blocks: list[dict[str, object]] = [
            {
                "type": "text",
                "text": system_prompt,
                **(
                    {"cache_control": {"type": "ephemeral"}}
                    if cache_system_prompt
                    else {}
                ),
            }
        ]

        try:
            # Stream so high max_tokens cannot trip the SDK's HTTP timeout.
            async with self._client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system_blocks,
                thinking={"type": "adaptive"},
                messages=[{"role": m.role, "content": m.content} for m in messages],
            ) as stream:
                final = await stream.get_final_message()
        except Exception as exc:  # noqa: BLE001 - re-wrap as a domain error
            raise ExternalServiceError(f"anthropic call failed: {exc}") from exc

        text_parts = [block.text for block in final.content if block.type == "text"]
        return LLMResponse(
            text="".join(text_parts),
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
            cache_read_input_tokens=getattr(
                final.usage, "cache_read_input_tokens", 0
            )
            or 0,
            cache_creation_input_tokens=getattr(
                final.usage, "cache_creation_input_tokens", 0
            )
            or 0,
        )
