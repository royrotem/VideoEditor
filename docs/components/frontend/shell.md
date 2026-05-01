# Component: Frontend / Shell

> The Next.js App Router shell - root layout, fonts, RTL setup, and the
> placeholder landing page.

## Purpose

Provide the outermost frame of the web app: HTML language attributes,
direction (`rtl`), Hebrew typography (Heebo), Tailwind base styles, and a
placeholder landing page until the real screens land in later phases.

This component is the only place that should set `<html dir>` or load
global stylesheets.

## Public interface

- `src/app/layout.tsx` - root layout. Renders `<html lang="he" dir="rtl">`
  and applies the Heebo font as a CSS variable.
- `src/app/page.tsx` - landing page placeholder.
- `src/app/globals.css` - Tailwind base + the body font-family.

## Inputs

None. The shell does not yet read from the backend.

## Outputs

A rendered HTML document with RTL Hebrew layout and Tailwind utilities
ready to use.

## Dependencies

- Next.js 15 (App Router).
- `next/font/google` for the Heebo font.
- TailwindCSS.

## Errors

None.

## How to test

- `pnpm test` runs vitest against `src/app/page.test.tsx`.
- Manual: `pnpm dev`, open <http://localhost:3000>, confirm the page is
  RTL and the Hebrew title renders.

## Change log notes

- LTR exceptions inside the page (e.g. embedded English code blocks) MUST
  set `dir="ltr"` on a wrapping element - the shell is RTL by default.
