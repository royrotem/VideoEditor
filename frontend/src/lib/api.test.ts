/**
 * Unit tests for the typed API client.
 *
 * `fetch` is mocked at the global level; tests assert request shape
 * and response handling, not network behaviour.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, projectsApi } from "./api";

type FetchMock = ReturnType<typeof vi.fn<typeof fetch>>;

function mockFetchOnce(body: unknown, init: ResponseInit = { status: 200 }) {
  const fn = vi.fn(async () => new Response(JSON.stringify(body), init)) as FetchMock;
  global.fetch = fn as unknown as typeof fetch;
  return fn;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("projectsApi.create", () => {
  it("POSTs JSON body to /api/projects and returns the parsed response", async () => {
    const fetched = mockFetchOnce(
      { id: "proj-1", name: "demo", description: null },
      { status: 201 },
    );

    const result = await projectsApi.create({ name: "demo", description: null });

    expect(result).toEqual({ id: "proj-1", name: "demo", description: null });
    expect(fetched).toHaveBeenCalledTimes(1);
    const call = fetched.mock.calls[0];
    expect(call).toBeDefined();
    const [url, init] = call!;
    expect(url).toBe("/api/projects");
    expect(init?.method).toBe("POST");
    expect((init?.headers as Record<string, string>)["content-type"]).toBe(
      "application/json",
    );
    expect(init?.body).toBe(JSON.stringify({ name: "demo", description: null }));
  });
});

describe("projectsApi.list", () => {
  it("returns the parsed list of projects on success", async () => {
    mockFetchOnce([{ id: "p1" }, { id: "p2" }]);

    const result = await projectsApi.list();
    expect(result).toEqual([{ id: "p1" }, { id: "p2" }]);
  });

  it("throws an ApiError carrying the backend error envelope", async () => {
    mockFetchOnce(
      { error: { code: "resource.not_found", message: "missing" } },
      { status: 404, statusText: "Not Found" },
    );

    await expect(projectsApi.list()).rejects.toMatchObject({
      status: 404,
      code: "resource.not_found",
      message: "missing",
    });
  });

  it("falls back to status text when the body is not JSON", async () => {
    const fn = vi.fn(
      async () =>
        new Response("not json", {
          status: 500,
          statusText: "Internal Server Error",
        }),
    ) as FetchMock;
    global.fetch = fn as unknown as typeof fetch;

    await expect(projectsApi.list()).rejects.toMatchObject({
      status: 500,
      code: "http_error",
      message: "Internal Server Error",
    });
  });
});

describe("ApiError", () => {
  it("is thrown with the correct shape", () => {
    const err = new ApiError(422, "validation.failed", "no good");
    expect(err.status).toBe(422);
    expect(err.code).toBe("validation.failed");
    expect(err.message).toBe("no good");
    expect(err).toBeInstanceOf(Error);
  });
});
