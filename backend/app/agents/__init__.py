"""Claude-backed agent network.

The agent network turns a free-text Hebrew brief into a structured Edit
Decision List (EDL). The framework here is the plumbing - prompts,
contracts, registry, and an Anthropic client wrapper. Concrete agents
(Creative Director, Editing Planner, Vision Analyzer, ...) plug into
the registry in subsequent commits.
"""

from app.agents.base import Agent, AgentInput, AgentOutput, ChatAgent
from app.agents.client import AnthropicLLMClient, LLMClient, LLMMessage, LLMResponse
from app.agents.registry import AgentRegistry, get_registry

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
