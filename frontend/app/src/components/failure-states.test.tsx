import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { resetHealth } from "@/lib/health";

import { ConnectionBanner } from "./connection-banner";
import { WakeGate } from "./wake-gate";

const ok = () => new Response('{"ok":true}', { status: 200 });
const down = () => new Response("Bad gateway", { status: 502 });

/** /healthz answers in order; anything else is a network failure. */
function stubHealth(...answers: (() => Response)[]) {
  let n = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (input) => {
      if (String(input) !== "/healthz") throw new TypeError("Failed to fetch");
      const answer = answers[Math.min(n, answers.length - 1)]!;
      n++;
      return answer();
    }),
  );
}

const renderGate = (props: { budgetMs?: number; wakingAfterMs?: number } = {}) =>
  render(
    <MemoryRouter>
      <WakeGate {...props}>
        <p>The page</p>
      </WakeGate>
    </MemoryRouter>,
  );

beforeEach(() => resetHealth());
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("<WakeGate>", () => {
  it("says the site isn't connected yet, at once, when the deploy has no backend", () => {
    vi.stubEnv("VITE_BACKEND_CONFIGURED", "0");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderGate();
    expect(screen.getByText("This site isn't connected to a server yet")).toBeTruthy();
    expect(screen.queryByText("The page")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled(); // no 90 s of pointless /healthz pings
    vi.unstubAllEnvs();
  });

  it("shows the page straight away when the backend answers", async () => {
    stubHealth(ok);
    renderGate();
    expect(await screen.findByText("The page")).toBeTruthy();
    expect(screen.queryByText("Waking up your front desk…")).toBeNull();
  });

  it("says the site isn't connected at once when /healthz is a 404 (no rewrite to a backend)", async () => {
    stubHealth(() => new Response("Not found", { status: 404 }));
    renderGate();
    expect(await screen.findByText("This site isn't connected to a server yet")).toBeTruthy();
    expect(screen.queryByText("Waking up your front desk…")).toBeNull();
  });

  it("shows the waking screen while the backend wakes, then the page", async () => {
    vi.useFakeTimers();
    stubHealth(down, down, ok);
    renderGate({ wakingAfterMs: 500 });
    await act(() => vi.advanceTimersByTimeAsync(600));
    expect(screen.getByText("Waking up your front desk…")).toBeTruthy();
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(screen.getByText("The page")).toBeTruthy();
  });

  it("offers a retry when the backend never answers", async () => {
    vi.useFakeTimers();
    stubHealth(down, down, down, ok);
    renderGate({ budgetMs: 2500, wakingAfterMs: 500 });
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(screen.getByText("Catalyst isn't responding")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Try again/ }));
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(screen.getByText("The page")).toBeTruthy();
  });
});

describe("<ConnectionBanner>", () => {
  it("appears when an API call can't reach the backend, retries, and goes away when it's back", async () => {
    vi.useFakeTimers();
    stubHealth(down, ok);
    render(<ConnectionBanner />);
    expect(screen.queryByText(/Can't reach Catalyst/)).toBeNull();

    await act(async () => {
      await api("/api/me").catch(() => {});
    });
    expect(screen.getByText(/Can't reach Catalyst right now/)).toBeTruthy();
    expect(screen.getByText(/Retrying in 2 s/)).toBeTruthy();

    // Step the clock so React can re-run its effects between ticks, as it does in real time.
    for (let i = 0; i < 5; i++) await act(() => vi.advanceTimersByTimeAsync(500)); // first retry: still down
    expect(screen.getByText(/Retrying in 4 s/)).toBeTruthy();

    const reconnected = vi.fn();
    window.addEventListener("catalyst:reconnected", reconnected);
    fireEvent.click(screen.getByRole("button", { name: "Retry now" })); // second ping: back
    await act(() => vi.advanceTimersByTimeAsync(100));
    expect(screen.queryByText(/Can't reach Catalyst/)).toBeNull();
    expect(reconnected).toHaveBeenCalledTimes(1);
    window.removeEventListener("catalyst:reconnected", reconnected);
  });

  it("treats a bare 500 from the dev proxy as trouble, but not the backend's own 500", async () => {
    let backendBody = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        backendBody
          ? new Response(JSON.stringify({ detail: "Something went wrong on our side.", code: "INTERNAL" }), {
              status: 500,
              headers: { "Content-Type": "application/json" },
            })
          : new Response("", { status: 500 }),
      ),
    );
    const { unmount } = render(<ConnectionBanner />);
    backendBody = true;
    await act(async () => {
      await api("/api/me").catch(() => {});
    });
    expect(screen.queryByText(/Can't reach Catalyst/)).toBeNull();
    backendBody = false;
    await act(async () => {
      await api("/api/me").catch(() => {});
    });
    expect(screen.getByText(/Can't reach Catalyst right now/)).toBeTruthy();
    unmount();
  });

  it("ignores the backend's deliberate 503 VOICE_NOT_CONFIGURED", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: "Voice isn't set up.", code: "VOICE_NOT_CONFIGURED" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    render(<ConnectionBanner />);
    await act(async () => {
      await api("/api/try/x/start", { method: "POST" }).catch(() => {});
    });
    expect(screen.queryByText(/Can't reach Catalyst/)).toBeNull();
  });
});
