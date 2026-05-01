# Agent Network

This document catalogues every Claude-backed agent in the system. Each
agent has a one-page component doc under `docs/components/agents/<name>.md`;
this file is the index and shows how they fit together.

## Network diagram

```
                        +------------------+
                        |   Orchestrator   |
                        |   (Opus 4.7)     |
                        +---+---+---+---+--+
                            |   |   |   |
       +--------------------+   |   |   +-----------------+
       |                        |   |                     |
+------v-------+   +------------v-+ |  +------------------v---+
| Vision       |   | Creative     | |  | QA Reviewer          |
| Analyzer     |   | Director     | |  | (Sonnet 4.6)         |
| (Sonnet 4.6) |   | (Opus 4.7)   | |  +----------------------+
+------+-------+   +------+-------+ |
       |                  |         |
       v                  v         v
   asset facts        approved   EDL pipeline
                       brief     +-------------------+
                                 |  Editing Planner  |
                                 |  (Sonnet 4.6)     |
                                 +---+---+---+---+---+
                                     |   |   |   |
                            +--------+   |   |   +----------+
                            v            v   v              v
                     +-----------+ +---------+ +----------+ +-----------+
                     | Cut Spec. | | Audio   | | Color/Fx | | Subtitles |
                     |(Sonnet)   | |(Haiku)  | |(Sonnet)  | |(Haiku)    |
                     +-----------+ +---------+ +----------+ +-----------+
```

## Agents

| Agent              | Model        | Role                                                              | Status |
| ------------------ | ------------ | ----------------------------------------------------------------- | ------ |
| Orchestrator       | claude-opus-4-7 | Owns the session state machine, decides which agent runs next  | scaffolded |
| Vision Analyzer    | claude-sonnet-4-6 | Extracts shots, motion, faces, dominant colors, audio energy | planned |
| [Creative Director](components/agents/creative-director.md) | claude-opus-4-7 | Holds the iterative Hebrew dialogue, proposes a plan | implemented |
| [Brief Extractor](components/agents/brief-extractor.md) | claude-sonnet-4-6 | Distills an approved chat into a structured BriefPlan | implemented |
| Editing Planner    | claude-sonnet-4-6 | Translates approved plan to a structured EDL                 | planned |
| Cut Specialist     | claude-sonnet-4-6 | Picks cut points, transitions, pacing                        | planned |
| Audio Engineer     | claude-haiku-4-5  | Music selection, ducking, voice-over alignment               | planned |
| Color / Effects    | claude-sonnet-4-6 | Color grade and effect parameters                            | planned |
| Subtitle / Text    | claude-haiku-4-5  | Hebrew subtitles, on-screen text, kinetic typography         | planned |
| QA Reviewer        | claude-sonnet-4-6 | Compares the EDL (and the rendered output) to the brief      | planned |

## Framework

The shared plumbing - base classes, registry, orchestrator, LLM client -
lives in `backend/app/agents/` and is documented in
[`components/agents/framework.md`](components/agents/framework.md).
Every concrete agent in the table above is a thin subclass that sets a
system prompt, picks a model, and declares its output model.

## Inter-agent contract

All agents speak through Pydantic models defined in
`backend/app/agents/contracts.py`. No agent receives or returns a free-form
`dict`. Examples:

- `AssetFacts` - what Vision Analyzer emits per asset.
- `BriefPlan` - what Creative Director hands to the Planner.
- `EditDecisionList` - what Planner / Specialists produce and the
  pipeline consumes.
- `QAReport` - what QA Reviewer emits.

## Adding a new agent

1. Create `backend/app/agents/<name>.py` that exposes:
   - `SYSTEM_PROMPT: str`
   - `MODEL: str`
   - `async def run(input: <InputModel>) -> <OutputModel>`
2. Register the agent in `backend/app/agents/registry.py`.
3. Add a component doc at `docs/components/agents/<name>.md` from
   `docs/COMPONENT_TEMPLATE.md`.
4. Update this file's table and diagram.
