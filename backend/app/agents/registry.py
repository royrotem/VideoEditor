"""Agent registry.

A tiny lookup table mapping agent names to their classes. The
orchestrator and the API layer instantiate agents by name through the
registry rather than importing each class directly. This keeps the
wiring in one place and makes it easy to swap implementations in tests.
"""

from __future__ import annotations

from typing import TypeVar

from app.agents.base import Agent, ChatAgent
from app.agents.client import LLMClient
from app.core.errors import NotFoundError

AnyAgent = Agent | ChatAgent  # type: ignore[type-arg]
T = TypeVar("T", bound=AnyAgent)


class AgentRegistry:
    """Holds agent classes keyed by name.

    Registration is at module import time via :meth:`register`; lookups
    at runtime via :meth:`build`. The registry is not thread-safe, but
    it is also append-only after startup, so that does not matter.
    """

    def __init__(self) -> None:
        self._classes: dict[str, type[AnyAgent]] = {}

    def register(self, agent_cls: type[T]) -> type[T]:
        """Register ``agent_cls`` under its declared :attr:`name`.

        Usable as a decorator::

            @get_registry().register
            class CreativeDirector(ChatAgent):
                name = "creative_director"
                ...
        """
        name = getattr(agent_cls, "name", None)
        if not name or name in {"agent", "chat_agent"}:
            raise ValueError(
                f"agent class {agent_cls.__name__} must declare a unique 'name'"
            )
        if name in self._classes:
            raise ValueError(f"agent name {name!r} is already registered")
        self._classes[name] = agent_cls
        return agent_cls

    def build(self, name: str, llm: LLMClient) -> AnyAgent:
        """Instantiate the agent registered under ``name``."""
        cls = self._classes.get(name)
        if cls is None:
            raise NotFoundError(f"agent {name!r} is not registered")
        return cls(llm)

    def names(self) -> list[str]:
        """Names of every registered agent, sorted for stable display."""
        return sorted(self._classes)


_REGISTRY = AgentRegistry()


def get_registry() -> AgentRegistry:
    """Return the process-wide registry singleton."""
    return _REGISTRY
