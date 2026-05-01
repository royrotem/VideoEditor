# Component: Frontend / Chat & Render Pages

> The screens that drive the agent flow: list / open chat sessions,
> hold the Hebrew dialogue with the Creative Director, and turn the
> approved brief into a rendered video the user can watch in-page.

## Purpose

Connect the user to the agent network and the deterministic render
pipeline, on a single per-project surface. Once an agent flow lands
in the backend, it should land here within one branch so the user
can actually exercise it.

## Routes

| Path                                        | Component                                            | Role                                          |
| ------------------------------------------- | ---------------------------------------------------- | --------------------------------------------- |
| `/projects/[id]/sessions`                   | `app/projects/[id]/sessions/page.tsx`                | List existing sessions; start a new one       |
| `/projects/[id]/sessions/[sid]`             | `app/projects/[id]/sessions/[sid]/page.tsx`          | Chat thread → brief → plan → submit render    |
| `/projects/[id]/renders`                    | `app/projects/[id]/renders/page.tsx`                 | List render jobs and play the selected one   |

The project detail page (`/projects/[id]`) gained two link cards
("שיחות עריכה" / "רנדרים") so the new screens are discoverable.

## Sub-components

| Module                                          | Role                                                                |
| ----------------------------------------------- | ------------------------------------------------------------------- |
| `components/chat/message-bubble.tsx`            | Single turn; user vs. agent vs. closing-summary styling             |
| `components/chat/message-list.tsx`              | Scrollable thread; auto-scrolls; hides the synthetic BRIEF turn     |
| `components/chat/message-input.tsx`             | Textarea + send; Cmd/Ctrl-Enter shortcut; locks when converged      |
| `components/chat/brief-summary.tsx`             | Read-only render of a `BriefPlan`                                   |
| `components/sessions/session-list.tsx`          | Pure presentational session list with `active` / `closed` badges    |
| `components/sessions/start-session-form.tsx`    | Brief textarea → `sessionsApi.start` → push to chat page            |
| `components/renders/render-list.tsx`            | Selectable list of jobs with `JobStatusBadge`                       |
| `components/renders/render-player.tsx`          | HTML5 video bound to a presigned URL fetched per `jobId`            |

## Chat → render flow (single page)

The chat page orchestrates the full path on one screen. State lives
in a few `useState` hooks — no global store needed for one project
at a time.

```
fetch /sessions/{id}/messages          ──▶  thread
user types + sends ──▶ POST /sessions/{id}/messages ──▶ append + check converged
converged becomes true ──▶ "גזור brief" button shows
click ──▶ POST /sessions/{id}/extract-brief ──▶ <BriefSummary>
"תכנן עריכה" ──▶ POST /projects/{id}/plan-edit ──▶ EDL (opaque to UI)
"הפק רנדר" ──▶ POST /projects/{id}/render ──▶ router.push to /renders
```

Convergence detection is sticky: the page sets a boolean once the
backend returns `converged: true`, and it also runs through the
existing thread on first load (so reloading after a "סיכום:" turn
still shows the post-chat actions).

## Renders page polling

The renders page polls `GET /projects/{id}/render-jobs` every four
seconds while at least one job is `pending` or `running`. It stops
polling automatically when every job reaches a terminal status.
Once we move the renderer onto a Celery worker we'll swap this for a
WebSocket or SSE stream — the page contract is already set up to
accept any source of `RenderJob[]` updates.

## Errors

Every API call surfaces failures as `<Alert>` blocks rather than
unhandled promise rejections. The page is designed to be idempotent
on retry — retry triggers a fresh load, never a duplicate session
or render.

## How to test

- `components/chat/message-list.test.tsx` covers BRIEF filtering,
  empty state, and rendering both roles.
- `components/chat/brief-summary.test.tsx` covers the "with style /
  music" and the "minimal" variants.
- `components/renders/render-list.test.tsx` covers empty + populated
  + click delegation.
- The pages themselves (with their async effects, navigation, and
  multi-step flows) are integration-shaped and will be covered by
  Playwright once we add the e2e harness.

## Change log notes

- The chat page hides the synthetic first user turn (BRIEF +
  ASSET_FACTS) — that payload is meant for the LLM, not the user.
  Filter logic lives in `MessageList`.
- `renderApi.outputUrl` returns a presigned URL that expires after
  one hour. `RenderPlayer` re-mounts on `jobId` change so a stale
  URL never lingers across selections.
- Page-level data fetching uses `AbortController` where supported
  (the player) so unmount during a slow request doesn't update
  removed React state.
