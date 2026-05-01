# Component: Agents / Framework

> The plumbing that lets Claude-backed agents talk to each other and to
> the rest of the application. Concrete agents (Creative Director,
> Editing Planner, Vision Analyzer, QA Reviewer, specialists) plug in
> via the registry; this component is what they all share.

## Purpose

Provide a tiny, opinionated framework so that:

- every agent has the same shape (one input model in, one output model
  out) and is therefore trivial to swap, test, or replay,
- the LLM client is injectable, so unit tests never touch the network,
- prompt caching, adaptive thinking, and streaming defaults are set
  once in :class:`AnthropicLLMClient` rather than copy-pasted into each
  agent,
- the inter-agent vocabulary is a small set of Pydantic models in
  ``contracts.py`` (no free-form dicts cross agent boundaries).

## Public interface

```python
# Contracts (Pydantic) — every value that crosses an agent boundary
class AssetFacts(BaseModel): ...
class BriefPlan(BaseModel): ...
class EditDecisionList(BaseModel): ...   # also consumed by the pipeline
class QAReport(BaseModel): ...

# LLM client protocol + production impl
class LLMClient(Protocol):
    async def complete(self, *, model, system_prompt, messages, ...) -> LLMResponse: ...

class AnthropicLLMClient(LLMClient): ...  # AsyncAnthropic-backed

# Agent base classes
class Agent(Generic[InputT, OutputT]):
    name: str; model: str; system_prompt: str; output_model: type[OutputT]
    async def run(self, input_payload: InputT) -> OutputT: ...

class ChatAgent:                          # multi-turn (Creative Director)
    async def reply(self, history: list[LLMMessage]) -> str: ...

# Registry + orchestrator
class AgentRegistry:
    def register(self, agent_cls: type) -> type: ...
    def build(self, name: str, llm: LLMClient) -> Agent | ChatAgent: ...

class Orchestrator:
    async def analyze_asset(self, asset_input) -> AssetFacts: ...
    async def plan_edit(self, *, brief, asset_facts, previous_edl=None) -> EditDecisionList: ...
    async def review_edl(self, *, brief, edl) -> QAReport: ...
```

## Inputs

Single-shot agents receive a Pydantic input model, which is serialised
to JSON and used as the user message. ChatAgents receive a list of
:class:`LLMMessage` (the running conversation).

## Outputs

Single-shot agents return their declared :attr:`output_model` instance.
The base class:

1. calls the LLM with the system prompt and the JSON-encoded input,
2. strips a Markdown code fence if present (`` ```json `` … `` ``` ``),
3. parses the text as JSON,
4. validates the result against the agent's output model.

Any failure in steps 3-4 is re-raised as
:class:`app.core.errors.ExternalServiceError` so callers see a stable
error type.

## Dependencies

- ``anthropic`` SDK (production LLM client only).
- :mod:`pydantic` for every contract.
- :mod:`app.core.config.Settings` for model IDs and the API key.
- :mod:`app.core.errors` for :class:`ExternalServiceError`.

## Errors

| Error                  | When                                                  |
| ---------------------- | ----------------------------------------------------- |
| `ExternalServiceError` | Anthropic API failure, non-JSON reply, schema mismatch |
| `NotFoundError`        | Registry asked for an unknown agent                    |
| `AppError`             | Orchestrator picks the wrong kind of agent (chat vs single-shot) |

## How to test

- ``backend/tests/test_agents.py`` exercises the base classes, the
  code-fence stripper, schema-validation failures, and the registry.
- ``backend/tests/test_orchestrator.py`` covers the routing methods
  with stub agents - no Anthropic calls.
- For real-network smoke tests we will wire one integration test in
  the `feature/creative-director-agent` branch behind an
  `ANTHROPIC_API_KEY` env guard so CI does not spend tokens.

## Change log notes

- The wire format between agents is **JSON only**. We instruct each
  agent in its system prompt to return a single JSON object that
  matches its :attr:`output_model`. Adding tool use is a future
  decision, not a default - the contract is intentionally narrow.
- The system prompt is cached (`cache_control: ephemeral`) so that
  multiple agent calls within the same session pay ~0.1× for the
  shared prefix. **Do not** interpolate per-request data into the
  system prompt - it would invalidate the cache.
- :class:`AnthropicLLMClient` uses ``messages.stream`` even for short
  replies, so high `max_tokens` values cannot trigger SDK HTTP
  timeouts.
