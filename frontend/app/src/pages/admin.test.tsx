import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Business, FeedbackRow } from "@/features/admin/api";

import { AdminPage } from "./admin";

// Fictional only (CLAUDE.md rule 6).
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const weeks = [
  { week_start: "2026-10-19", events: 4, records: 1, calls: 2, wa_commands: 0 },
  { week_start: "2026-10-26", events: 6, records: 2, calls: 3, wa_commands: 1 },
  { week_start: "2026-11-02", events: 8, records: 3, calls: 4, wa_commands: 1 },
  { week_start: "2026-11-09", events: 10, records: 4, calls: 5, wa_commands: 2 },
];

const BUSINESSES: Business[] = [
  { id: "t-demo", name: "Demo Clinic", public_id: "demo-clinic", template: "clinic", created_at: "2026-11-01", is_demo: true, users: 1, records: 50, calls: 60, wa_commands: 9, last_active: "2026-11-12T10:00:00+05:30", weeks },
  { id: "t-1", name: "Example Dental", public_id: "abc123", template: "clinic", created_at: "2026-11-05", is_demo: false, users: 2, records: 10, calls: 14, wa_commands: 4, last_active: "2026-11-12T09:00:00+05:30", weeks },
  { id: "t-2", name: "Example Traders", public_id: "def456", template: "wholesale", created_at: "2026-11-06", is_demo: false, users: 1, records: 5, calls: 3, wa_commands: 1, last_active: null, weeks },
];

const row = (over: Partial<FeedbackRow>): FeedbackRow => ({
  id: 1,
  business: "Example Dental",
  person_name: "Doctor A",
  person_role: "Owner",
  text: "Please show tomorrow's bookings on the home page.",
  type: "feature",
  decision: null,
  decision_reason: null,
  shipped_on: null,
  evidence_url: null,
  partner_reaction: null,
  created_at: "2026-11-11T12:00:00+05:30",
  ...over,
});

const FEEDBACK = [row({}), row({ id: 2, text: "The desk was slow once.", type: "bug", decision: "shipped", shipped_on: "2026-11-12" })];

type Handler = (init?: RequestInit) => Response;

function mockApi(overrides: Record<string, Handler> = {}) {
  const routes: Record<string, Handler> = {
    "/api/admin/businesses": () => json(200, { businesses: BUSINESSES }),
    "/api/admin/feedback": () => json(200, { feedback: FEEDBACK, types: [], decisions: [] }),
    ...overrides,
  };
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const handler = routes[String(input)];
    if (!handler) throw new Error(`unexpected fetch ${String(input)}`);
    return handler(init);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const renderPage = () =>
  render(
    <MemoryRouter>
      <AdminPage />
    </MemoryRouter>,
  );

afterEach(() => vi.unstubAllGlobals());

describe("<AdminPage>", () => {
  it("asks for the admin password when not logged in, then loads", async () => {
    let loggedIn = false;
    const unauth = () => json(401, { detail: "Please log in as admin to continue.", code: "UNAUTHENTICATED" });
    const fetchMock = mockApi({
      "/api/admin/businesses": () => (loggedIn ? json(200, { businesses: BUSINESSES }) : unauth()),
      "/api/admin/feedback": () => (loggedIn ? json(200, { feedback: FEEDBACK, types: [], decisions: [] }) : unauth()),
      "/api/admin/login": () => {
        loggedIn = true;
        return json(200, { ok: true });
      },
    });
    renderPage();
    fireEvent.change(await screen.findByLabelText("Admin password"), { target: { value: "a long team password" } });
    fireEvent.click(screen.getByRole("button", { name: /Log in/ }));
    expect(await screen.findByRole("heading", { name: "Team admin" })).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(([u]) => u === "/api/admin/login")!;
    expect(init?.headers).toMatchObject({ "X-Requested-With": "catalyst" });
  });

  it("shows the lockout message as the backend words it", async () => {
    mockApi({
      "/api/admin/businesses": () => json(401, { detail: "Please log in as admin to continue.", code: "UNAUTHENTICATED" }),
      "/api/admin/login": () => json(429, { detail: "Too many wrong passwords. Try again in 15 minutes.", code: "LOCKED" }),
    });
    renderPage();
    fireEvent.change(await screen.findByLabelText("Admin password"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /Log in/ }));
    expect(await screen.findByText("Too many wrong passwords. Try again in 15 minutes.")).toBeTruthy();
  });

  it("totals real businesses only and lists each with its weeks and CSV link", async () => {
    mockApi();
    renderPage();
    const list = await screen.findByRole("list", { name: "Businesses" });
    const totals = screen.getByText("Businesses").closest("dl")!;
    expect(within(totals).getByText("2")).toBeTruthy(); // the demo is left out
    expect(within(totals).getByText("15")).toBeTruthy(); // 10 + 5 records
    const cards = within(list).getAllByRole("listitem");
    expect(within(cards[0]!).getByText("Example Dental")).toBeTruthy(); // real ones first, demo last
    expect(within(cards[2]!).getByText("Demo")).toBeTruthy();
    expect(within(cards[0]!).getByRole("table", { name: /Last 4 weeks/ })).toBeTruthy();
    expect(within(cards[0]!).getByRole("link", { name: /Download usage CSV/ }).getAttribute("href")).toBe("/api/admin/businesses/t-1/usage.csv");
  });

  it("shows undecided feedback first and records a decision", async () => {
    const fetchMock = mockApi({
      "/api/admin/feedback/1": () => json(200, row({ decision: "planned", decision_reason: "Next week" })),
    });
    renderPage();
    fireEvent.click(await screen.findByRole("tab", { name: /Feedback \(1\)/ }));
    const list = screen.getByRole("list", { name: "Feedback" });
    expect(within(list).getByText("Please show tomorrow's bookings on the home page.")).toBeTruthy();
    expect(within(list).queryByText("The desk was slow once.")).toBeNull(); // decided: under All
    expect(screen.getByRole("link", { name: /Feedback CSV/ }).getAttribute("href")).toBe("/api/admin/feedback.csv");

    fireEvent.click(within(list).getByRole("button", { name: "Decide" }));
    const dialog = await screen.findByRole("dialog", { name: "Decision" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "Planned" }));
    fireEvent.change(within(dialog).getByLabelText("Why", { exact: false }), { target: { value: "Next week" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Save decision/ }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const [, init] = fetchMock.mock.calls.find(([u]) => u === "/api/admin/feedback/1")!;
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(String(init!.body))).toEqual({
      decision: "planned",
      decision_reason: "Next week",
      shipped_on: null,
      evidence_url: "",
      partner_reaction: "",
    });
    expect(screen.getByText("Everything has a decision")).toBeTruthy();
  });

  it("can clear a decision back to Undecided", async () => {
    const fetchMock = mockApi({ "/api/admin/feedback/2": () => json(200, row({ id: 2, text: "The desk was slow once.", type: "bug" })) });
    renderPage();
    fireEvent.click(await screen.findByRole("tab", { name: /Feedback/ }));
    fireEvent.click(screen.getByRole("button", { name: /^All/ }));
    fireEvent.click(screen.getByRole("button", { name: "Change decision" }));
    const dialog = await screen.findByRole("dialog", { name: "Decision" });
    expect(within(dialog).getByRole("radio", { name: "Shipped" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(within(dialog).getByRole("radio", { name: "Undecided" }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Save decision/ }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const [, init] = fetchMock.mock.calls.find(([u]) => u === "/api/admin/feedback/2")!;
    expect(JSON.parse(String(init!.body)).decision).toBeNull();
  });

  it("needs a reason for won't do, and an https evidence link", async () => {
    const fetchMock = mockApi();
    renderPage();
    fireEvent.click(await screen.findByRole("tab", { name: /Feedback/ }));
    fireEvent.click(screen.getByRole("button", { name: "Decide" }));
    const dialog = await screen.findByRole("dialog", { name: "Decision" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "Won't do" }));
    fireEvent.change(within(dialog).getByLabelText("Evidence link", { exact: false }), { target: { value: "http://example.com" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Save decision/ }));
    expect(await within(dialog).findByText("Say why it won't be done.")).toBeTruthy();
    expect(within(dialog).getByText("Evidence must be a link starting with https://.")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([u]) => u === "/api/admin/feedback/1")).toBe(false);
  });
});
