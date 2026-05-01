"""Deterministic media pipeline.

The pipeline is the LLM-free part of the system. It accepts an
:class:`~app.agents.contracts.EditDecisionList` produced by the agent
network and turns it into a rendered file in object storage.

Stage modules land here as the pipeline grows. The first one is
:mod:`app.pipeline.edl_validator` - structural validation of an EDL
against the assets that actually exist for a project. Validation runs
before rendering and (eventually) right after the planner emits an EDL
so we can ask for a revision rather than ship a bad render.
"""

from app.pipeline.edl_validator import (
    EdlValidator,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)

__all__ = [
    "EdlValidator",
    "ValidationIssue",
    "ValidationReport",
    "ValidationSeverity",
]
