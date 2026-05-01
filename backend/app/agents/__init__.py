"""Claude-backed agent network.

The agent network turns a free-text Hebrew brief into a structured Edit
Decision List (EDL). The framework here is the plumbing - prompts,
contracts, registry, and an Anthropic client wrapper. Concrete agents
are imported eagerly so that their ``@get_registry().register``
decorators run on package import.
"""

from app.agents.base import Agent, AgentInput, AgentOutput, ChatAgent
from app.agents.client import AnthropicLLMClient, LLMClient, LLMMessage, LLMResponse
from app.agents.registry import AgentRegistry, get_registry

# Side-effect imports: each module decorates its agent class with
# ``@get_registry().register`` at import time. Keeping the imports here
# means the rest of the codebase only has to ``import app.agents`` to
# populate the registry.
from app.agents import brief_extractor as _brief_extractor  # noqa: F401
from app.agents import creative_director as _creative_director  # noqa: F401
from app.agents import editing_planner as _editing_planner  # noqa: F401

__all__ = [
    "Agent",
    "AgentInput",
    "AgentOutput",
    "ChatAgent",
    "AnthropicLLMClient",
    "LLMClient",
    "LLMMessage",
    "LLMResponse",
    "AgentRegistry",
    "get_registry",
]
