"""Cross-cutting concerns: configuration, logging, error types.

Nothing in this package may import from `app.api`, `app.agents`, or
`app.pipeline` - those are the leaves; `core` is a leaf-of-leaves.
"""
