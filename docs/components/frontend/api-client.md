# Component: Frontend / API Client

> Typed `fetch`-based client mapping every backend endpoint the
> frontend uses today. One module, one place to look when an endpoint
> changes.

## Purpose

Centralise the URL strings, payload shapes, and error parsing so
pages stay declarative. Anything page-specific (state, optimistic
updates, polling) belongs to the consumers; this module is purely
"call the API, parse the response, throw a typed error on failure".

All requests go through `/api/*`, which `next.config.mjs` rewrites
to the configured backend host. Same code path works in dev (proxied
to `localhost:8000`) and in deployed environments (proxied to the
real backend).

## Public interface

```ts
class ApiError extends Error {
  status: number;
  code: string;        // backend's stable error code, e.g. "asset.not_found"
}

const projectsApi = {
  list, get, create,
};

const assetsApi = {
  list, upload, reanalyze, presignedUrl,
};

const sessionsApi = {
  start, list, messages, send, extractBrief,
};

const renderApi = {
  submit, list, get, outputUrl,
};
```

Wire-format types live in `src/lib/types.ts` and mirror the backend's
Pydantic schemas (Project, Asset, Session, Message, RenderJob, etc.).

## Errors

`ApiError` carries:

- `status` — HTTP status code,
- `code` — the backend's stable code from
  `{ error: { code, message } }`, defaulting to `"http_error"` when
  the response body is not JSON,
- `message` — caller-safe Hebrew/English string.

Use `instanceof ApiError` in components to render the message; fall
through to a generic Hebrew error string for everything else.

## How to test

`src/lib/api.test.ts` mocks `global.fetch` and asserts:

- the request URL, method, headers and body for one POST endpoint,
- a 2xx body is returned as parsed JSON,
- a 4xx with a structured envelope becomes an `ApiError`,
- a non-JSON failure body falls back to status-text.

## Change log notes

- `__internal.request` is exported so tests / new features can hook
  the same wrapper without re-implementing JSON / error parsing.
- New endpoints land here, not in components. If a page reaches for
  `fetch` directly, that's a smell.
