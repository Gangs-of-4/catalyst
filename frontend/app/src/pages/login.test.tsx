import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { safeNext } from "@/lib/session";

import { LoginPage } from "./login";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const UNAUTH = () => json(401, { detail: "Please log in to continue.", code: "UNAUTHENTICATED" });

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
  return <p data-testid="where">{loc.pathname}</p>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );
}

const type = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const submit = () => fireEvent.click(screen.getByRole("button", { name: "Log in" }));

afterEach(() => vi.unstubAllGlobals());

describe("<LoginPage>", () => {
  it("logs in and goes to the home page", async () => {
    const fetchMock = mockApi({
      "/api/me": UNAUTH,
      "/api/login": () => json(200, { public_id: "abc123", template: "clinic" }),
    });
    renderAt("/login");
    type("Email", " owner@example.com ");
    type("Password", "long enough");
    submit();
    expect((await screen.findByTestId("where")).textContent).toBe("/home");
    const [, init] = fetchMock.mock.calls.find(([url]) => url === "/api/login")!;
    expect(JSON.parse(String(init?.body))).toEqual({ email: "owner@example.com", password: "long enough" });
    expect(init?.headers).toMatchObject({ "X-Requested-With": "catalyst" });
  });

  it("returns to a same-app ?next= path after login", async () => {
    mockApi({ "/api/me": UNAUTH, "/api/login": () => json(200, { public_id: "abc123", template: "clinic" }) });
    renderAt("/login?next=/settings");
    type("Email", "owner@example.com");
    type("Password", "long enough");
    submit();
    expect((await screen.findByTestId("where")).textContent).toBe("/settings");
  });

  it("shows the server's sentence for wrong details and clears the password", async () => {
    mockApi({
      "/api/me": UNAUTH,
      "/api/login": () => json(401, { detail: "That email or password is wrong.", code: "UNAUTHENTICATED" }),
    });
    renderAt("/login");
    type("Email", "owner@example.com");
    type("Password", "wrong one");
    submit();
    expect(await screen.findByText("That email or password is wrong.")).toBeTruthy();
    expect((screen.getByLabelText("Password") as HTMLInputElement).value).toBe("");
  });

  it("explains a locked account", async () => {
    mockApi({
      "/api/me": UNAUTH,
      "/api/login": () =>
        json(429, { detail: "Too many wrong passwords. Please wait 15 minutes and try again.", code: "LOCKED" }),
    });
    renderAt("/login");
    type("Email", "owner@example.com");
    type("Password", "wrong one");
    submit();
    expect(await screen.findByText(/wait 15 minutes/)).toBeTruthy();
  });

  it("checks the fields before sending anything", async () => {
    const fetchMock = mockApi({ "/api/me": UNAUTH });
    renderAt("/login");
    submit();
    expect(await screen.findByText("Enter an email like name@example.com.")).toBeTruthy();
    expect(screen.getByText("Please fill in your password.")).toBeTruthy();
    await waitFor(() => expect(fetchMock.mock.calls.every(([url]) => url === "/api/me")).toBe(true));
  });

  it("skips the form when already logged in", async () => {
    mockApi({
      "/api/me": () =>
        json(200, {
          user: { name: "Test Owner", email: "owner@example.com" },
          business: { name: "Example Dental", template: "clinic", public_id: "abc123", labels: {} },
        }),
    });
    renderAt("/login");
    expect((await screen.findByTestId("where")).textContent).toBe("/home");
  });
});

describe("safeNext", () => {
  it.each([
    [null, "/home"],
    ["/settings", "/settings"],
    ["https://evil.example", "/home"],
    ["//evil.example", "/home"],
    ["/\\evil.example", "/home"],
    ["settings", "/home"],
  ])("%j → %s", (next, want) => expect(safeNext(next)).toBe(want));
});
