# Component: API / Sessions

> Chat sessions between the user and the agent network. Surfaces the
> Creative Director's iterative dialogue and the Brief Extractor's
> structured output as plain HTTP routes.

## Purpose

Connect the Hebrew chat UI to the agent network:

1. The user opens a session for a project, optionally with assets.
2. Each user turn is sent to the Creative Director; both turns are
   persisted in the ``messages`` table.
3. When the Director's reply starts with ``"סיכום:"`` (the convergence
   marker), the session is closed automatically and the frontend can
   call ``POST /sessions/{id}/extract-brief`` to get a structured
   :class:`BriefPlan` for the Editing Planner.

## Public interface

| Method | Path                                              | Body / Returns                          |
| ------ | ------------------------------------------------- | --------------------------------------- |
| POST   | `/projects/{id}/sessions`                         | `{brief}` -> `StartSessionResponse` 201 |
| GET    | `/projects/{id}/sessions`                         | -> `list[SessionRead]`                  |
| GET    | `/sessions/{id}/messages`                         | -> `list[MessageRead]`                  |
| POST   | `/sessions/{id}/messages`                         | `{content}` -> `AssistantReply` 201     |
| POST   | `/sessions/{id}/extract-brief`                    | -> `BriefPlan`                          |

Schemas live in `backend/app/schemas/sessions.py`. The
`AssistantReply.converged` boolean is the signal for the frontend to
invite the user to confirm the plan and proceed to extraction.

## Inputs / outputs

- The opening turn is built server-side via
  :meth:`CreativeDirector.build_opening_user_message` so the asset
  facts get injected next to the brief. Only the ``brief`` string from
  the request body is shown in the chat UI.
- Subsequent user turns flow through unchanged.
- Once the Director emits a ``"סיכום:"`` reply, the session moves to
  ``status = closed`` automatically.

## Dependencies

- :class:`ChatService` (`app.services.chat`) for orchestration.
- :class:`SessionRepository`, :class:`MessageRepository`,
  :class:`ProjectRepository`, :class:`AssetRepository`.
- :class:`LLMClient` (production: :class:`AnthropicLLMClient`).
- The Creative Director and Brief Extractor agents.

## Errors

| Error                        | When                                          | HTTP |
| ---------------------------- | --------------------------------------------- | ---- |
| `validation.failed`          | Empty brief or message, or session is closed   | 422  |
| `resource.not_found`         | Project or session id is unknown               | 404  |
| `external.failed`            | Anthropic call failed or returned bad JSON     | 502  |

## How to test

- Service-level: ``backend/tests/test_chat_service.py`` covers
  start_session, send_turn, convergence + auto-close, and
  extract_brief - all against a scripted in-memory LLM.
- HTTP-level: ``backend/tests/test_routes_sessions.py`` exercises
  every route via FastAPI dependency overrides.
- Integration (later): a smoke test that calls the real Anthropic API
  behind an `ANTHROPIC_API_KEY` env guard.

## Change log notes

- The opening user message is what the LLM sees, **not** what the
  frontend renders. The frontend should display only the brief the
  user typed; the persisted user message contains the brief plus the
  ASSET_FACTS header.
- Token-by-token streaming will land in a follow-up branch; it
  requires extending :class:`LLMClient` with a streaming interface.
  Today every reply round-trips as a single HTTP response.
