import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Business, BusinessDetail, Overview, Totals } from "./api";
import { Dashboard } from "./dashboard";

// Fictional only (CLAUDE.md rule 6).
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const weeks = [{ week_start: "2026-11-09", events: 10, records: 4, calls: 5, wa_commands: 2 }];
const BUSINESSES: Business[] = [
  { id: "t-1", name: "Example Dental", public_id: "a", template: "clinic", created_at: "2026-11-05", is_demo: false, users: 2, records: 10, calls: 14, wa_commands: 4, last_active: new Date().toISOString(), weeks },
  { id: "t-d", name: "Demo Clinic", public_id: "demo-clinic", template: "clinic", created_at: "2026-11-01", is_demo: true, users: 1, records: 50, calls: 60, wa_commands: 9, last_active: null, weeks },
];

const totals = (over: Partial<Totals> = {}): Totals => ({
  businesses: 1,
  active_businesses_7d: 1,
  users: 2,
  active_users_7d: 2,
  calls: 14,
  call_minutes: 97,
  records: { bookings: 10, orders: 0 },
  records_by_source: { phone: 7, walk_in: 3 },
  wa_commands: 4,
  feedback: 1,
  app_minutes: 135,
  ...over,
});

const OVERVIEW: Overview = {
  generated_at: "2026-11-13T10:00:00+05:30",
  real: totals(),
  demo: totals({ businesses: 2, calls: 60, call_minutes: 240 }),
  features: [
    { type: "booking_status", count: 30 },
    { type: "settings_saved", count: 6 },
    { type: "login", count: 0 },
  ],
  daily: [
    { date: "2026-11-11", active_businesses: 1, events: 5, calls: 2, call_minutes: 4.5, app_minutes: 20 },
    { date: "2026-11-12", active_businesses: 1, events: 9, calls: 3, call_minutes: 7, app_minutes: 35 },
  ],
};

const DETAIL: BusinessDetail = {
  business: BUSINESSES[0]!,
  features: [{ type: "booking_created", count: 12 }],
  daily: OVERVIEW.daily,
  users: [
    { id: "u-1", role: "owner", last_active: null, logins: 5, app_minutes: 90, active_days: 4 },
    { id: "u-2", role: "staff", last_active: null, logins: 2, app_minutes: 45, active_days: 2 },
  ],
};

function mockApi(routes: Record<string, () => Response>) {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    const handler = routes[String(input)];
    if (!handler) throw new Error(`unexpected fetch ${String(input)}`);
    return handler();
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const renderDash = () => render(<Dashboard businesses={BUSINESSES} onAuthError={() => false} />);
const tile = (label: string) => screen.getByText(label, { selector: "dt" }).parentElement!;

afterEach(() => vi.unstubAllGlobals());

describe("<Dashboard>", () => {
  it("shows the headline numbers, including call minutes and time in the app", async () => {
    mockApi({ "/api/admin/overview?scope=real": () => json(200, OVERVIEW) });
    renderDash();
    await waitFor(() => expect(within(tile("Calls answered")).getByText("1 h 37 min on calls")).toBeTruthy());
    expect(within(tile("Time in the app")).getByText("2 h 15 min")).toBeTruthy();
    expect(within(tile("Made by the AI")).getByText("7")).toBeTruthy();
    expect(within(tile("Businesses")).getByText("1 active this week")).toBeTruthy();
  });

  it("lists what was used in plain words, biggest first, leaving out zeros", async () => {
    mockApi({ "/api/admin/overview?scope=real": () => json(200, OVERVIEW) });
    renderDash();
    const section = (await screen.findByRole("heading", { name: "What they used" })).closest("section")!;
    const items = within(section).getAllByRole("listitem").map((li) => li.textContent);
    expect(items[0]).toContain("Appointments marked");
    expect(items[1]).toContain("Settings saved");
    expect(within(section).queryByText("Logged in")).toBeNull();
    const sources = (screen.getByRole("heading", { name: /Who made the bookings/ })).closest("section")!;
    expect(within(sources).getByText("By the AI on the phone")).toBeTruthy();
  });

  it("switches the daily measure and can show it as a table", async () => {
    mockApi({ "/api/admin/overview?scope=real": () => json(200, OVERVIEW) });
    renderDash();
    // Businesses per day can't be added up: the busiest day is shown instead.
    expect(await screen.findByText(/Active businesses, last 2 days, most in one day:/)).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Call minutes" }));
    expect(screen.getByText(/Call minutes, last 2 days:/)).toBeTruthy();
    expect(screen.getByRole("listitem", { name: "12 Nov: 7 min" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Show as table" }));
    const table = screen.getByRole("table", { name: "Call minutes per day" });
    expect(within(table).getByText("4.5")).toBeTruthy();
  });

  it("asks for the demo numbers when switched to Demo", async () => {
    const fetchMock = mockApi({
      "/api/admin/overview?scope=real": () => json(200, OVERVIEW),
      "/api/admin/overview?scope=demo": () => json(200, OVERVIEW),
    });
    renderDash();
    await screen.findByText("1 h 37 min on calls");
    fireEvent.click(screen.getByRole("button", { name: "Demo" }));
    await waitFor(() => expect(within(tile("Calls answered")).getByText("4 h on calls")).toBeTruthy());
    expect(fetchMock.mock.calls.some(([u]) => u === "/api/admin/overview?scope=demo")).toBe(true);
    expect(screen.getByRole("button", { name: /Demo Clinic/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Example Dental/ })).toBeNull();
  });

  it("still shows what it can when the overview endpoint isn't live yet", async () => {
    mockApi({ "/api/admin/overview?scope=real": () => json(404, { detail: "We couldn't find that.", code: "NOT_FOUND" }) });
    renderDash();
    expect(await screen.findByText(/arrive with the backend update in issue #56/)).toBeTruthy();
    expect(within(tile("Calls answered")).getByText("14")).toBeTruthy(); // from the usage list
    expect(screen.queryByRole("heading", { name: "Day by day" })).toBeNull();
  });

  it("opens one business with its people as counts only", async () => {
    mockApi({
      "/api/admin/overview?scope=real": () => json(200, OVERVIEW),
      "/api/admin/businesses/t-1": () => json(200, DETAIL),
    });
    renderDash();
    fireEvent.click(await screen.findByRole("button", { name: /Example Dental/ }));
    const dialog = await screen.findByRole("dialog", { name: "Example Dental" });
    const people = await within(dialog).findByRole("table", { name: /People at Example Dental/ });
    expect(within(people).getByText("1 h 30 min")).toBeTruthy();
    expect(within(people).queryByText(/@/)).toBeNull(); // never an email
    expect(within(dialog).getByText("Appointments booked")).toBeTruthy();
  });
});
