import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { pingHealth, recentlyHealthy, resetHealth, waitForBackend } from "./health";

const ok = () => new Response('{"ok":true}', { status: 200 });
const down = () => new Response("Bad gateway", { status: 502 });

function stubFetch(...answers: (() => Response | Promise<Response>)[]) {
  let n = 0;
  const fn = vi.fn<typeof fetch>(async () => {
    const answer = answers[Math.min(n, answers.length - 1)]!;
    n++;
    return answer();
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => resetHealth());
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("pingHealth", () => {
  it("is true for a 2xx and remembers it", async () => {
    stubFetch(ok);
    expect(await pingHealth()).toBe(true);
    expect(recentlyHealthy()).toBe(true);
  });

  it("is false for a 502 or a network failure", async () => {
    stubFetch(down);
    expect(await pingHealth()).toBe(false);
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    expect(await pingHealth()).toBe(false);
    expect(recentlyHealthy()).toBe(false);
  });
});

describe("waitForBackend", () => {
  it("skips the check when the backend answered recently", async () => {
    stubFetch(ok);
    await pingHealth();
    const fetchMock = stubFetch(ok);
    expect(await waitForBackend()).toBe(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps trying while the backend wakes up, and says it's waking", async () => {
    vi.useFakeTimers();
    const fetchMock = stubFetch(down, down, ok);
    const onWaking = vi.fn();
    const result = waitForBackend({ onWaking, budgetMs: 60_000 });
    await vi.advanceTimersByTimeAsync(10_000);
    expect(await result).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(onWaking).toHaveBeenCalledTimes(1);
  });

  it("gives up when the budget runs out", async () => {
    vi.useFakeTimers();
    stubFetch(down);
    const result = waitForBackend({ budgetMs: 5000 });
    await vi.advanceTimersByTimeAsync(10_000);
    expect(await result).toBe(false);
  });
});
