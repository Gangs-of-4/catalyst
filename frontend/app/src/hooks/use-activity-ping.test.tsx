import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PING_MS, useActivityPing } from "./use-activity-ping";

function Probe() {
  useActivityPing();
  return null;
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

beforeEach(() => {
  vi.useFakeTimers();
  fetchMock = vi.fn<typeof fetch>(async () => new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const minute = async () => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(PING_MS);
  });
};

describe("useActivityPing", () => {
  it("pings once a minute only when the person did something that minute", async () => {
    render(<Probe />);
    await minute();
    expect(fetchMock).not.toHaveBeenCalled(); // idle: not counted

    fireEvent.pointerDown(window);
    await minute();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/activity");
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({ "X-Requested-With": "catalyst" });
    expect(init?.body).toBeUndefined(); // nothing about the page or the person

    await minute(); // no new tap or keypress since
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("stops for the visit when the backend doesn't have the endpoint yet", async () => {
    fetchMock.mockImplementation(async () => json(404, { detail: "We couldn't find that.", code: "NOT_FOUND" }));
    render(<Probe />);
    fireEvent.keyDown(window, { key: "a" });
    await minute();
    fireEvent.keyDown(window, { key: "b" });
    await minute();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("doesn't count a hidden tab", async () => {
    const spy = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    render(<Probe />);
    fireEvent.pointerDown(window);
    await minute();
    expect(fetchMock).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});
