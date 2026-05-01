# Component: Agents / Brief Extractor

> Single-shot agent that turns an approved Creative-Director conversation
> into a structured :class:`BriefPlan`.

## Purpose

The Creative Director leaves the editing plan in free-form Hebrew.
The Brief Extractor reads that conversation and emits the same
information as a strict, validated :class:`BriefPlan` JSON object so
the downstream Editing Planner has a deterministic input.

It runs once per editing session, immediately after
:func:`is_approval_message` matches on the Director's last reply.

## Public interface

```python
class BriefExtractor(Agent[ConversationTranscript, BriefPlan]):
    name = "brief_extractor"
    model = "claude-sonnet-4-6"
    system_prompt = BRIEF_EXTRACTOR_SYSTEM_PROMPT
    output_model = BriefPlan

class ConversationTranscript(BaseModel):
    turns: list[LLMMessageDict]

    @classmethod
    def from_messages(cls, messages: list[LLMMessage]) -> "ConversationTranscript": ...

class LLMMessageDict(BaseModel):
    role: str
    content: str
```

## Inputs

A :class:`ConversationTranscript` - a flat list of role / content turns.
Build it via :meth:`ConversationTranscript.from_messages` from the same
:class:`LLMMessage` history the Creative Director used.

## Outputs

A :class:`app.agents.contracts.BriefPlan`. Defaults documented in the
system prompt: 60 second target duration if unset, ``"medium"`` pacing
if unspecified, ``music_direction = null`` if music wasn't discussed.

## Dependencies

- :class:`app.agents.base.Agent` (handles JSON parsing + Pydantic
  validation).
- :data:`app.agents.prompts.brief_extractor.BRIEF_EXTRACTOR_SYSTEM_PROMPT`.

## Errors

| Error                  | When                                                                |
| ---------------------- | ------------------------------------------------------------------- |
| `ExternalServiceError` | Model returned non-JSON or a JSON object that doesn't match the schema |

## How to test

``backend/tests/test_creative_director.py`` covers happy path (a valid
JSON reply parsed into a :class:`BriefPlan`), transcript formatting
(``[משתמש]`` / ``[במאי]`` speaker tags), the model choice, and
non-JSON failure mode.

## Change log notes

- Sonnet 4.6 is used (not Opus 4.7) because this is a small, schema-
  bound extraction task with no reasoning load.
- The system prompt forbids code fences, but the base
  :class:`Agent._parse_output` strips them anyway as a safety net.
