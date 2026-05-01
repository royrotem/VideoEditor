# Component Documentation

This directory holds one Markdown file per component. Each follows
[`../COMPONENT_TEMPLATE.md`](../COMPONENT_TEMPLATE.md).

Component docs are part of the contract for that component. **If you
change the component, update its doc in the same commit.**

## Index

Subdirectories mirror the source layout:

- `agents/` - one file per Claude agent.
- `pipeline/` - one file per pipeline stage / module.
- `api/` - one file per FastAPI route group.
- `storage/` - one file per storage adapter.
- `frontend/` - one file per frontend feature.

When you add a new component, also link it from the relevant high-level
doc (`ARCHITECTURE.md`, `AGENTS.md`, or `PIPELINE.md`).
