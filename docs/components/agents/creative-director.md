# Component: Agents / Creative Director

> Hebrew, multi-turn conversational agent that iterates with the user
> until they approve a concrete editing direction.

## Purpose

Translate a free-text idea like *"רוצה משהו קצר ואנרגטי מהחתונה של
אחותי"* into a concrete plan an automation pipeline can act on. The
Creative Director does **not** do any editing itself - it just
converges on a plan in dialogue, then signals approval so the
:doc:`Brief Extractor <brief-extractor>` can produce a structured
:class:`BriefPlan`.

The conversation is always Hebrew, second person, warm but
professional. Turns are short and proposal-led ("יש לי שתי הצעות, A
ו-B…") rather than question-led, so the user converges fast.

## Public interface

```python
class CreativeDirector(ChatAgent):
    name = "creative_director"
    model = "claude-opus-4-7"
    system_prompt = CREATIVE_DIRECTOR_SYSTEM_PROMPT

    @staticmethod
    def build_opening_user_message(*, brief: str, asset_facts: list[AssetFacts]) -> LLMMessage: ...

# Marker the Director's closing message starts with.
APPROVAL_MARKER = "סיכום:"

def is_approval_message(text: str) -> bool: ...
```

## Inputs

- **First user turn**: built via :meth:`build_opening_user_message`.
  Contains the user's natural-language brief plus a JSON dump of the
  Vision Analyzer's :class:`AssetFacts` for every uploaded asset under
  an ``ASSET_FACTS`` header.
- **Subsequent user turns**: plain text, appended to the conversation
  history.

## Outputs

A free-form Hebrew assistant turn. When the user has approved a
direction, the model is instructed to start its closing message with
the literal token ``"סיכום:"`` so the surrounding orchestration code
(API layer, tests) can detect convergence by calling
:func:`is_approval_message`.

## Dependencies

- :class:`app.agents.base.ChatAgent`.
- :class:`app.agents.client.LLMClient` (production:
  :class:`AnthropicLLMClient`).
- :data:`app.agents.prompts.creative_director.CREATIVE_DIRECTOR_SYSTEM_PROMPT`.

## Errors

The agent itself does not raise; the underlying
:class:`AnthropicLLMClient` re-wraps SDK failures as
:class:`ExternalServiceError`.

## How to test

- Unit: ``backend/tests/test_creative_director.py`` covers opening
  message formatting, approval-marker detection, and that the agent
  is registered under its declared name.
- Integration (later): a smoke test against the real Anthropic API,
  guarded by ``ANTHROPIC_API_KEY`` so CI does not spend tokens.

## Change log notes

- The approval marker is a contract between the system prompt and
  ``is_approval_message``. **Change them together, never separately.**
- ``ASSET_FACTS`` is rendered as JSON because the Brief Extractor (and
  any future agent that reads the conversation) can re-parse it
  deterministically.
