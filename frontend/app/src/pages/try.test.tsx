import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BookingsBoard, OrdersBoard, TryInfo } from "@/features/try/api";
import { type CallEvents, MicBlockedError } from "@/lib/voice";

import { DemoRedirect, TryPage } from "./try";

const startCallMock = vi.fn();
vi.mock("@/lib/voice", async () => {
  const actual = await vi.importActual<typeof import("@/lib/voice")>("@/lib/voice");
  return {
    ...actual,
    // If the spy returns an Error, throw it here, outside the spy, as the real startCall would.
    startCall: async (...args: unknown[]) => {
      const result = await startCallMock(...args);
      if (result instanceof Error) throw result;
      return result;
    },
  };
});

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const INFO: TryInfo = {
  public_id: "abc123",
  name: "Example Dental",
  city: "Pune",
  template: "clinic",
  modules: ["bookings"],
  labels: { resource: "Doctor", booking: "Appointment", tenant: "Clinic" },
  voice: { public_key: "pk_test", assistant_id: "asst_test" },
  try_saying: ["Kal subah appointment chahiye", "Sunday ko khula hai?"],
};

function bookings(extra: { time: string; id: number; name: string }[] = []): BookingsBoard {
  const slots = [
    { time: "10:00", state: "booked" as const, booking: { id: 1, name: "Ramesh G.", source: "phone" as const } },
    { time: "10:15", state: "free" as const, booking: null },
    ...extra.map((e) => ({
      time: e.time,
      state: "booked" as const,
      booking: { id: e.id, name: e.name, source: "phone" as const },
    })),
  ];
  return {
    kind: "bookings",
    days: [{ date: "2026-11-11", label: "Today", short: "Wed, 11 Nov", closed: false, columns: [{ resource: "Doctor A", slots }] }],
  };
}

type Handler = (init?: RequestInit) => Response;

function mockApi(routes: Record<string, Handler | Handler[]>) {
  const calls: Record<string, number> = {};
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const key = `${init?.method ?? "GET"} ${String(input)}`;
    const route = routes[key];
    if (!route) throw new Error(`unexpected fetch ${key}`);
    const n = (calls[key] = (calls[key] ?? 0) + 1);
    const handler = Array.isArray(route) ? route[Math.min(n, route.length) - 1]! : route;
    return handler(init);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname}</p>;
}

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/b/:publicId/try" element={<TryPage />} />
        <Route path="/demo/:template" element={<DemoRedirect />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => startCallMock.mockReset());
afterEach(() => vi.unstubAllGlobals());

describe("<TryPage>", () => {
  it("shows the business, the try-saying lines and the board", async () => {
    mockApi({ "GET /api/try/abc123": () => json(200, INFO), "GET /api/try/abc123/board": () => json(200, bookings()) });
    renderAt("/b/abc123/try");
    expect(await screen.findByRole("heading", { name: "Example Dental" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Talk to your front desk" })).toBeTruthy();
    expect(screen.getByText(/Kal subah appointment chahiye/)).toBeTruthy();
    expect(await screen.findByText("Ramesh G.")).toBeTruthy();
    expect(screen.getByText("Appointment register")).toBeTruthy();
  });

  it("explains when the voice agent isn't switched on", async () => {
    mockApi({
      "GET /api/try/abc123": () => json(200, { ...INFO, voice: null }),
      "GET /api/try/abc123/board": () => json(200, bookings()),
    });
    renderAt("/b/abc123/try");
    expect(await screen.findByText("The voice agent isn't switched on yet")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Talk to your front desk" })).toBeNull();
  });

  it("says so when the business doesn't exist", async () => {
    mockApi({ "GET /api/try/nope": () => json(404, { detail: "Not found.", code: "NOT_FOUND" }) });
    renderAt("/b/nope/try");
    expect(await screen.findByText("This front desk doesn't exist")).toBeTruthy();
  });

  it("checks the cap, starts the call, shows what's said, and refreshes the board after", async () => {
    let events: CallEvents | undefined;
    const stop = vi.fn();
    startCallMock.mockImplementation(async (_key: string, _asst: string, ev: CallEvents) => {
      events = ev;
      return { stop };
    });
    const fetchMock = mockApi({
      "GET /api/try/abc123": () => json(200, INFO),
      "GET /api/try/abc123/board": [
        () => json(200, bookings()),
        () => json(200, bookings([{ time: "10:30", id: 2, name: "Sita K." }])),
      ],
      "POST /api/try/abc123/start": () => json(200, { max_call_seconds: 180 }),
    });
    renderAt("/b/abc123/try");
    await screen.findByText("Ramesh G.");

    fireEvent.click(screen.getByRole("button", { name: "Talk to your front desk" }));
    await waitFor(() => expect(startCallMock).toHaveBeenCalledWith("pk_test", "asst_test", expect.any(Object)));
    const [, init] = fetchMock.mock.calls.find(([url, i]) => url === "/api/try/abc123/start" && i?.method === "POST")!;
    expect(init?.headers).toMatchObject({ "X-Requested-With": "catalyst" });

    act(() => events!.onLive());
    expect(await screen.findByRole("button", { name: "End the call" })).toBeTruthy();
    expect(screen.getByText("Live")).toBeTruthy();
    act(() => events!.onTranscript("assistant", "Namaste, Example Dental."));
    expect(screen.getByText("Namaste, Example Dental.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "End the call" }));
    expect(stop).toHaveBeenCalled();
    act(() => events!.onEnded());
    expect(await screen.findByRole("button", { name: "Talk to your front desk" })).toBeTruthy();
    // The booking made during the call shows up, marked as new.
    expect(await screen.findByText("Sita K.")).toBeTruthy();
    expect(screen.getByText(/New ·/)).toBeTruthy();
  });

  it("shows the server's sentence when today's minutes are used up, without starting a call", async () => {
    mockApi({
      "GET /api/try/abc123": () => json(200, INFO),
      "GET /api/try/abc123/board": () => json(200, bookings()),
      "POST /api/try/abc123/start": () =>
        json(429, { detail: "Today's free demo minutes are used up. Please try again tomorrow.", code: "MINUTES_USED_UP" }),
    });
    renderAt("/b/abc123/try");
    fireEvent.click(await screen.findByRole("button", { name: "Talk to your front desk" }));
    expect(await screen.findByText(/demo minutes are used up/)).toBeTruthy();
    expect(startCallMock).not.toHaveBeenCalled();
  });

  it("gives a one-line fix when the microphone is blocked", async () => {
    startCallMock.mockReturnValue(new MicBlockedError());
    mockApi({
      "GET /api/try/abc123": () => json(200, INFO),
      "GET /api/try/abc123/board": () => json(200, bookings()),
      "POST /api/try/abc123/start": () => json(200, { max_call_seconds: 180 }),
    });
    renderAt("/b/abc123/try");
    fireEvent.click(await screen.findByRole("button", { name: "Talk to your front desk" }));
    expect(await screen.findByText(/blocked the microphone/)).toBeTruthy();
  });

  it("shows an orders board for an orders template", async () => {
    const orders: OrdersBoard = {
      kind: "orders",
      orders: [
        { id: 3, number: "A-102", shop: "Ramesh G.", items: 3, total: "₹2,400", status: "new", source: "phone", created_at: "2026-11-11T10:30:00+05:30" },
      ],
    };
    mockApi({
      "GET /api/try/w1": () => json(200, { ...INFO, public_id: "w1", template: "wholesale", modules: ["orders"] }),
      "GET /api/try/w1/board": () => json(200, orders),
    });
    renderAt("/b/w1/try");
    expect(await screen.findByText("Today's orders")).toBeTruthy();
    expect(await screen.findByText("A-102 · Ramesh G.")).toBeTruthy();
    expect(screen.getByText("3 items · ₹2,400")).toBeTruthy();
  });
});

describe("<DemoRedirect>", () => {
  it("opens the demo business's test page", async () => {
    mockApi({
      "GET /api/try/demo-clinic": () => json(200, { ...INFO, public_id: "demo-clinic" }),
      "GET /api/try/demo-clinic/board": () => json(200, bookings()),
    });
    renderAt("/demo/clinic");
    expect(await screen.findByRole("heading", { name: "Example Dental" })).toBeTruthy();
  });

  it("treats a malformed template as not found", () => {
    render(
      <MemoryRouter initialEntries={["/demo/../admin"]}>
        <Routes>
          <Route path="/demo/:template" element={<DemoRedirect />} />
          <Route path="*" element={<DemoRedirect />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("This page doesn't exist")).toBeTruthy();
  });
});
