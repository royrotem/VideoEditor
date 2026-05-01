# Component: Frontend / Projects Pages

> The two pages that bracket the editing flow: a home page that
> lists / creates projects, and a per-project detail page that hosts
> the asset list and upload affordance.

## Purpose

Give the user a way to organise their work and feed raw material
into the agent network. Everything chat- and render-related lives on
follow-up screens; this layer is the ingress.

## Routes

| Path                    | Component                                          | What it shows                          |
| ----------------------- | -------------------------------------------------- | -------------------------------------- |
| `/`                     | `src/app/page.tsx`                                 | Project list + new-project form        |
| `/projects/[id]`        | `src/app/projects/[id]/page.tsx`                   | Project metadata + asset list + uploader |

Both pages are client components - data is per-user and we want
post-mutation refresh without a full reload. Server-side rendering is
on the table once authentication lands.

## Sub-components

| Module                                       | Role                                               |
| -------------------------------------------- | -------------------------------------------------- |
| `components/projects/new-project-form.tsx`   | Inline form; calls `projectsApi.create`            |
| `components/projects/project-list.tsx`       | Pure presentational list with empty-state hint     |
| `components/assets/asset-uploader.tsx`       | File picker + `assetsApi.upload`; shows "loading"  |
| `components/assets/asset-list.tsx`           | Pure presentational table; status badges          |
| `components/ui/button.tsx`                   | `<button>` with primary/secondary/ghost variants  |
| `components/ui/status-badge.tsx`             | `AssetStatusBadge`, `JobStatusBadge`              |
| `components/ui/alert.tsx`                    | Inline error / info banner                         |

## Data flow

```
HomePage / ProjectPage
    │
    └─ useEffect → projectsApi / assetsApi
                       │
                       ▼
                 ApiError → <Alert>
                       │
                       ▼
                 Project[] / Asset[] → presentational lists
```

After a successful mutation (create project, upload asset) the page
calls its own `refresh()` callback. The lists are pure functions of
their props, so re-fetching + setting state is enough to update.

## Errors

- API failures bubble up as `ApiError` and render as `<Alert>` with
  the backend's `error.message`.
- Generic exceptions (network down, JSON parse failure on a non-JSON
  body) fall back to a Hebrew "שגיאה לא צפויה" string.

## How to test

- `src/lib/api.test.ts` and `src/lib/format.test.ts` cover the lower
  layers.
- `src/components/projects/project-list.test.tsx` and
  `src/components/assets/asset-list.test.tsx` cover the
  presentational components - empty state, populated state, links
  / status badges.

The forms (`NewProjectForm`, `AssetUploader`) are integration-shaped
and will be covered by Playwright once we add the e2e harness.

## Change log notes

- Asset upload runs `ffprobe` + the Vision Analyzer inline on the
  backend; a single upload may take a few seconds. The uploader
  button locks into a loading state for the duration so users don't
  re-trigger it.
- The projects route is intentionally simple - sessions / render
  controls live on a follow-up `/projects/[id]/sessions/[sid]` and
  `/projects/[id]/renders` page set, landing in
  `feature/frontend-chat-and-render`.
