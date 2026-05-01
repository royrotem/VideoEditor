# Component: <Name>

> One-line description of what this component is for.

## Purpose

Why does this component exist? What problem does it solve? What is **not**
its job (so callers don't misuse it)?

## Public interface

The functions, classes, routes, or events this component exposes.
For a Python module, list the public names and their signatures. For an
agent, list its system prompt location, input model, output model, and
which model it uses.

```python
# Example
def render_edl(edl: EditDecisionList, output_spec: OutputSpec) -> RenderResult: ...
```

## Inputs

The shape of the data this component consumes. Reference the Pydantic
model name and its file.

## Outputs

The shape of what this component returns or emits.

## Dependencies

- Other internal modules used (with paths).
- External services / libraries.
- Environment variables read.

## Errors

What this component raises, when, and how callers should react.

| Error                | When                          | Caller action                |
| -------------------- | ----------------------------- | ---------------------------- |
| `AssetNotFoundError` | EDL references a missing clip | Ask user to re-upload        |

## How to test

- Unit tests location and what they cover.
- Any fixtures or test containers required.
- Manual smoke test, if applicable.

## Change log notes

If this component has subtle invariants (ordering guarantees, idempotency,
performance constraints), record them here so future changes don't break
them.
