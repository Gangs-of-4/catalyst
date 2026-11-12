import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, NETWORK_ERROR } from "./api";

function mockFetch(response: Response | Error) {
  const fn = vi.fn<typeof fetch>(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("api()", () => {
  it("GETs a relative /api path with the cookie and no CSRF header", async () => {
    const fetchMock = mockFetch(json(200, { ok: true }));
    await expect(api("/api/me")).resolves.toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/me");
    expect(init?.credentials).toBe("same-origin");
    expect(init?.headers).not.toHaveProperty("X-Requested-With");
  });

  it("sends JSON writes with the CSRF header the backend requires", async () => {
    const fetchMock = mockFetch(json(200, { public_id: "abc" }));
    await api("/api/login", { method: "POST", body: { email: "owner@example.com", password: "x" } });
    const [, init] = fetchMock.mock.calls[0]!;
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({
      "X-Requested-With": "catalyst",
      "Content-Type": "application/json",
    });
    expect(init?.body).toBe(JSON.stringify({ email: "owner@example.com", password: "x" }));
  });

  it("sends a raw body (a CSV file) with its own content type and the CSRF header", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => new Response(JSON.stringify({ added: 1 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const csv = "name,rate\nA,1\n";
    await api("/api/catalog/import", { method: "POST", raw: { body: csv, contentType: "text/csv" } });
    const [, init] = fetchMock.mock.calls[0]!;
    expect(init?.headers).toMatchObject({ "Content-Type": "text/csv", "X-Requested-With": "catalyst" });
    expect(init?.body).toBe(csv);
  });

  it("turns the contracts §6 error shape into an ApiError with field messages", async () => {
    mockFetch(
      json(422, {
        detail: "Enter an email like name@example.com.",
        code: "VALIDATION",
        fields: { "user.email": "Enter an email like name@example.com." },
      }),
    );
    const err = await api("/api/signup", { method: "POST", body: {} }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      status: 422,
      code: "VALIDATION",
      message: "Enter an email like name@example.com.",
      fields: { "user.email": "Enter an email like name@example.com." },
    });
  });

  it("falls back to a plain sentence when the body isn't the error shape", async () => {
    mockFetch(new Response("<html>Bad gateway</html>", { status: 502 }));
    await expect(api("/api/me")).rejects.toMatchObject({ code: "INTERNAL", status: 502 });
  });

  it("reports a network failure in plain words", async () => {
    mockFetch(new TypeError("Failed to fetch"));
    await expect(api("/api/me")).rejects.toMatchObject({ status: 0, ...NETWORK_ERROR });
  });

  it("refuses absolute URLs so pages can't bypass the rewrite", async () => {
    await expect(api("https://example.com/api/me")).rejects.toThrow(/relative \/api\//);
  });
});
