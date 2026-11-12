import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Booking, Day, Slot } from "@/features/desk/api";

import { DeskPage } from "./desk";

// Fictional only (CLAUDE.md rule 6).
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const ME = {
  user: { name: "Test Owner", email: "owner@example.com" },
  business: {
    name: "Example Dental",
    template: "clinic",
    public_id: "abc123",
    labels: { resource: "Doctor", resource_plural: "Doctors", booking: "Appointment" },
  },
};

const booking = (over: Partial<Booking>): Booking => ({
  id: 1,
  resource_id: "doc-a",
  date: "2026-11-12",
  time: "10:15",
  status: "booked",
  source: "phone",
  name: "Ramesh G",
  phone: "+919000000001",
  reason: null,
  ...over,
});

const slot = (time: string, over: Partial<Slot> = {}): Slot => ({
  time,
  state: "free",
  past: false,
  bookings: [],
  block: null,
  ...over,
});

function makeDay(date = "2026-11-12", label = "Today"): Day {
  return {
    date,
    closed: false,
    label,
    long: "Thursday, 12 November",
    short: "Thu 12 Nov",
    stray: [],
    columns: [
      {
        doctor: { id: "doc-a", name: "Doctor A" },
        slots: [
          slot("09:45", { state: "past", past: true }),
          slot("10:00", { state: "past", past: true }),
          slot("10:15", { state: "booked", bookings: [booking({})] }),
          slot("10:30"),
        ],
      },
      {
        doctor: { id: "doc-b", name: "Doctor B" },
        slots: [slot("10:15"), slot("10:30", { state: "blocked", block: "leave" })],
      },
    ],
  };
}

type Handler = (init?: RequestInit) => Response;

function mockApi(overrides: Record<string, Handler> = {}) {
  const routes: Record<string, Handler> = {
    "/api/me": () => json(200, ME),
    "/api/desk/day": () => json(200, makeDay()),
    "/api/inbox": () => json(200, []),
    "/api/calls": () => json(200, []),
    "/api/stats": () => json(200, { sentence: "2 calls today, 1 appointment.", urgent_open: 0, callbacks_open: 0, appointments: 1, calls: 2 }),
    ...overrides,
  };
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input);
    const handler = routes[url] ?? routes[url.split("?")[0]!];
    if (!handler) throw new Error(`unexpected fetch ${url}`);
    return handler(init);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderDesk() {
  return render(
    <MemoryRouter initialEntries={["/desk"]}>
      <Routes>
        <Route path="/desk" element={<DeskPage />} />
        <Route path="/login" element={<p>Login page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

const posts = (fetchMock: ReturnType<typeof mockApi>, url: string) =>
  fetchMock.mock.calls.filter(([u, init]) => u === url && init?.method === "POST");

afterEach(() => vi.unstubAllGlobals());

describe("<DeskPage>", () => {
  it("shows one doctor per tab, with the business and today's numbers", async () => {
    mockApi();
    renderDesk();
    expect(await screen.findByRole("heading", { name: "Example Dental" })).toBeTruthy();
    expect(screen.getByText("2 calls today, 1 appointment.")).toBeTruthy();

    const tabA = screen.getByRole("tab", { name: /Doctor A/ });
    const tabB = screen.getByRole("tab", { name: /Doctor B/ });
    expect(tabA.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("Ramesh G")).toBeTruthy();

    fireEvent.click(tabB);
    expect(tabB.getAttribute("aria-selected")).toBe("true");
    const panelB = screen.getByRole("tabpanel", { name: /Doctor B/ });
    expect(panelB.className).not.toContain("hidden");
    expect(within(panelB).getByText("On leave")).toBeTruthy();
  });

  it("folds earlier empty times away until asked", async () => {
    mockApi();
    renderDesk();
    const show = await screen.findByRole("button", { name: "Show 2 earlier times" });
    const panelA = screen.getByRole("tabpanel", { name: /Doctor A/ });
    expect(within(panelA).queryByText("9:45 am")).toBeNull();
    fireEvent.click(show);
    expect(within(panelA).getByText("9:45 am")).toBeTruthy();
  });

  it("adds a walk-in from a free time", async () => {
    const fetchMock = mockApi({ "/api/desk/bookings": () => json(200, { id: 9 }) });
    renderDesk();
    fireEvent.click(await screen.findByRole("button", { name: "Add a booking at 10:30 am with Doctor A" }));

    const dialog = await screen.findByRole("dialog", { name: "Add a booking" });
    expect(within(dialog).getByText(/Doctor A · 10:30 am · Today, Thu 12 Nov/)).toBeTruthy();
    fireEvent.change(within(dialog).getByLabelText("Patient's name"), { target: { value: "Sita K" } });
    fireEvent.change(within(dialog).getByLabelText(/Mobile number/), { target: { value: "90000 00002" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Save booking/ }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const [[, init]] = posts(fetchMock, "/api/desk/bookings") as [[string, RequestInit]];
    expect(init.headers).toMatchObject({ "X-Requested-With": "catalyst" });
    expect(JSON.parse(String(init.body))).toEqual({
      doctor_id: "doc-a",
      date: "2026-11-12",
      time: "10:30",
      name: "Sita K",
      phone: "90000 00002",
      source: "walk_in",
    });
  });

  it("asks for a name before sending anything", async () => {
    const fetchMock = mockApi();
    renderDesk();
    fireEvent.click(await screen.findByRole("button", { name: "Add a booking at 10:30 am with Doctor A" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /Save booking/ }));
    expect(await within(dialog).findByText("Please write the patient's name.")).toBeTruthy();
    expect(posts(fetchMock, "/api/desk/bookings")).toHaveLength(0);
  });

  it("offers the free times nearby when the slot was just taken, keeping what was typed", async () => {
    let calls = 0;
    const fetchMock = mockApi({
      "/api/desk/bookings": () =>
        ++calls === 1
          ? json(409, {
              detail: "That slot isn't free. Free nearby: 10:45 am Doctor A.",
              code: "SLOT_TAKEN",
              alternatives: [{ doctor_id: "doc-b", date: "2026-11-12", time: "10:45" }],
            })
          : json(200, { id: 10 }),
    });
    renderDesk();
    fireEvent.click(await screen.findByRole("button", { name: "Add a booking at 10:30 am with Doctor A" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Patient's name"), { target: { value: "Sita K" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Save booking/ }));

    const alt = await within(dialog).findByRole("button", { name: "10:45 am · Doctor B" });
    expect(within(dialog).getByText(/That slot isn't free/)).toBeTruthy();
    fireEvent.click(alt);
    expect(within(dialog).getByText(/Doctor B · 10:45 am/)).toBeTruthy();
    expect((within(dialog).getByLabelText("Patient's name") as HTMLInputElement).value).toBe("Sita K");

    fireEvent.click(within(dialog).getByRole("button", { name: /Save booking/ }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const body = JSON.parse(String(posts(fetchMock, "/api/desk/bookings")[1]![1]!.body));
    expect(body).toMatchObject({ doctor_id: "doc-b", time: "10:45", name: "Sita K" });
  });

  it("marks a patient arrived", async () => {
    const fetchMock = mockApi({ "/api/desk/bookings/1/status": () => json(200, { ok: true }) });
    renderDesk();
    fireEvent.click(await screen.findByRole("button", { name: "Arrived" }));
    await waitFor(() => expect(posts(fetchMock, "/api/desk/bookings/1/status")).toHaveLength(1));
    const [, init] = posts(fetchMock, "/api/desk/bookings/1/status")[0]!;
    expect(JSON.parse(String(init!.body))).toEqual({ status: "arrived" });
  });

  it("asks before cancelling", async () => {
    const fetchMock = mockApi({ "/api/desk/bookings/1/status": () => json(200, { ok: true }) });
    renderDesk();
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    const dialog = await screen.findByRole("dialog", { name: "Cancel this booking?" });
    expect(posts(fetchMock, "/api/desk/bookings/1/status")).toHaveLength(0);
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel booking" }));
    await waitFor(() => expect(posts(fetchMock, "/api/desk/bookings/1/status")).toHaveLength(1));
    const [, init] = posts(fetchMock, "/api/desk/bookings/1/status")[0]!;
    expect(JSON.parse(String(init!.body))).toEqual({ status: "cancelled" });
  });

  it("shows urgent inbox items first and marks them done", async () => {
    let open = true;
    const fetchMock = mockApi({
      "/api/inbox": () =>
        json(
          200,
          open
            ? [{ id: 5, kind: "escalation", urgent: 1, name: "Anil P", phone: null, reason: "red_flag", note: null, created_at: "2026-11-12T10:05:00+05:30" }]
            : [],
        ),
      "/api/inbox/5/done": () => {
        open = false;
        return json(200, { ok: true });
      },
    });
    renderDesk();
    expect(await screen.findByText(/1 urgent item needs you/)).toBeTruthy();
    expect(screen.getByText("Needs a doctor")).toBeTruthy();
    expect(screen.getByText("Red flag")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Mark done" }));
    await waitFor(() => expect(screen.getByText("Nothing waiting")).toBeTruthy());
    expect(posts(fetchMock, "/api/inbox/5/done")).toHaveLength(1);
  });

  it("moves to the next day", async () => {
    const fetchMock = mockApi({
      "/api/desk/day": () => json(200, makeDay()),
      "/api/desk/day?date=2026-11-13": () => json(200, { ...makeDay("2026-11-13", "Tomorrow"), short: "Fri 13 Nov" }),
    });
    renderDesk();
    fireEvent.click(await screen.findByRole("button", { name: "Next day" }));
    expect(await screen.findByText("Tomorrow")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([u]) => u === "/api/desk/day?date=2026-11-13")).toBe(true);
    expect(screen.getByRole("button", { name: "Today" })).toBeTruthy();
  });

  it("sends a logged-out visitor to login", async () => {
    mockApi({ "/api/me": () => json(401, { detail: "Please log in to continue.", code: "UNAUTHENTICATED" }) });
    renderDesk();
    expect(await screen.findByText("Login page")).toBeTruthy();
  });

  it("explains when the business takes orders instead of appointments", async () => {
    mockApi({ "/api/desk/day": () => json(404, { detail: "This business doesn't keep a schedule.", code: "NOT_FOUND" }) });
    renderDesk();
    expect(await screen.findByText("Your order board is on its way")).toBeTruthy();
  });
});
