# Component: API / Projects

> CRUD endpoints for the ``projects`` aggregate.

## Purpose

Surface the lifecycle of an editing project: create, list, fetch by id.
Projects are the root aggregate for everything else (assets, sessions,
EDL versions, render jobs).

## Public interface

| Method | Path                  | Body            | Response          |
| ------ | --------------------- | --------------- | ----------------- |
| POST   | `/projects`           | `ProjectCreate` | `ProjectRead` 201 |
| GET    | `/projects`           | -               | `list[ProjectRead]` |
| GET    | `/projects/{id}`      | -               | `ProjectRead`     |

Schemas live in `backend/app/schemas/projects.py`.

## Errors

- `404 resource.not_found` when fetching an unknown project id.

## How to test

- `backend/tests/test_routes_projects.py` covers the happy paths and
  the 404.

## Change log notes

- Update / delete endpoints will be added once we have authentication;
  today the API is single-user.
