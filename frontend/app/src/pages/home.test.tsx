import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "./home";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const ME = {
  user: { name: "Test Owner", email: "owner@example.com" },
  business: { name: "Example Dental", template: "clinic", public_id: "abc123", labels: { tenant: "Clinic" } },
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

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname + loc.search}</p>;
}

const renderHome = () =>
  render(
    <MemoryRouter initialEntries={["/home"]}>
      <Routes>
        <Route path="/home" element={<HomePage />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );

afterEach(() => vi.unstubAllGlobals());

describe("<HomePage>", () => {
  it("shows the logged-in owner's business", async () => {
    mockApi({ "/api/me": () => json(200, ME) });
    renderHome();
    expect(await screen.findByRole("heading", { name: "Example Dental" })).toBeTruthy();
    expect(screen.getByText("Hello, Test")).toBeTruthy();
    expect(screen.getByText("owner@example.com")).toBeTruthy();
    expect(screen.getByText("Your clinic")).toBeTruthy();
    // A clear next step: the business's own test page.
    expect(screen.getByRole("link", { name: "Open your test page" }).getAttribute("href")).toBe("/b/abc123/try");
  });

  it("sends a logged-out visitor to login, coming back here after", async () => {
    mockApi({ "/api/me": () => json(401, { detail: "Please log in to continue.", code: "UNAUTHENTICATED" }) });
    renderHome();
    expect((await screen.findByTestId("where")).textContent).toBe("/login?next=/home");
  });

  it("logs out and goes to the login page", async () => {
    const fetchMock = mockApi({ "/api/me": () => json(200, ME), "/api/logout": () => json(200, { ok: true }) });
    renderHome();
    fireEvent.click(await screen.findByRole("button", { name: "Log out" }));
    expect((await screen.findByTestId("where")).textContent).toBe("/login");
    const [, init] = fetchMock.mock.calls.find(([url]) => url === "/api/logout")!;
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({ "X-Requested-With": "catalyst" });
  });

  it("offers a retry when the backend can't be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    renderHome();
    expect(await screen.findByText("Your account didn't load")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Try again/ })).toBeTruthy();
  });
});
