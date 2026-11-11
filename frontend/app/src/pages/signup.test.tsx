import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CLINIC, WHOLESALE } from "@/test/fixtures";

import { SignupPage } from "./signup";

type Route = (init?: RequestInit) => Response;

function mockApi(routes: Record<string, Route>) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input);
    // Not logged in, unless a test says otherwise.
    const handler = routes[url] ?? (url === "/api/me" ? UNAUTH : undefined);
    if (!handler) throw new Error(`unexpected fetch ${url}`);
    return handler(init);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const templates = () => json(200, { templates: [CLINIC, WHOLESALE] });
const UNAUTH = () => json(401, { detail: "Please log in to continue.", code: "UNAUTHENTICATED" });
const ME = {
  user: { name: "Test Owner", email: "owner@example.com" },
  business: { name: "Example Dental", template: "clinic", public_id: "abc123", labels: {} },
};

function renderPage(path = "/signup") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <SignupPage />
    </MemoryRouter>,
  );
}

const type = (label: string | RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole("button", { name }));
const nextStep = () => click(/^Next/);
const submit = () => click("Create my front desk");
const stepLabel = () => screen.getByText(/^Step/).textContent;

/** Steps 1 and 2 filled, ending on step 3 (template already loaded). */
function fillToStep3() {
  type("Your name", "Test Owner");
  type("Email", "owner@example.com");
  type("Password", "long enough");
  nextStep();
  type("Clinic name", "Example Dental");
  type("Address", "1 Test Road");
  type("Your WhatsApp number", "90000 00001");
  nextStep();
}

function fillValidClinic() {
  fillToStep3();
  type("Doctor 1 name", "Doctor A");
  fireEvent.click(screen.getByRole("checkbox"));
}

afterEach(() => vi.unstubAllGlobals());

describe("<SignupPage>", () => {
  it("shows one step per screen, starting with step 1 of 3", async () => {
    mockApi({ "/api/templates": templates });
    renderPage();
    await screen.findByLabelText("Your name");
    expect(stepLabel()).toContain("1/3");
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("1");
    expect(screen.queryByLabelText("Address")).toBeNull(); // step 2 isn't on screen yet
    expect(screen.queryByRole("button", { name: /Back/ })).toBeNull(); // nothing to go back to
  });

  it("Next checks only this step's fields and stays put until they're fixed", async () => {
    const fetchMock = mockApi({ "/api/templates": templates });
    renderPage();
    await screen.findByLabelText("Your name");
    nextStep();
    expect(await screen.findByText("Please fix the highlighted fields.")).toBeTruthy();
    expect(screen.getByLabelText("Email").getAttribute("aria-invalid")).toBe("true");
    expect(stepLabel()).toContain("1/3");
    // Step 2's errors (address, WhatsApp...) aren't shown yet.
    expect(screen.queryByText("Please fill in your address.")).toBeNull();
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/signup")).toBe(false); // nothing sent
  });

  it("goes back without checking, keeping what was typed", async () => {
    mockApi({ "/api/templates": templates });
    renderPage();
    await screen.findByLabelText("Your name");
    type("Your name", "Test Owner");
    type("Email", "owner@example.com");
    type("Password", "long enough");
    nextStep();
    expect(stepLabel()).toContain("2/3");
    type("Clinic name", "Example Dental");
    click(/Back/);
    expect(stepLabel()).toContain("1/3");
    expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe("owner@example.com");
    nextStep();
    expect((screen.getByLabelText("Clinic name") as HTMLInputElement).value).toBe("Example Dental");
  });

  it("prefills the template's section on step 3", async () => {
    mockApi({ "/api/templates": templates });
    renderPage();
    expect(await screen.findByLabelText("Your name")).toBeTruthy();
    fillToStep3();
    expect(stepLabel()).toContain("3/3");
    expect(screen.getByRole("group", { name: "Doctors and services" })).toBeTruthy();
    expect((screen.getByLabelText("Service 1") as HTMLInputElement).value).toBe("Consultation");
  });

  it("shows the orders section on step 3 when the owner picks the other template", async () => {
    mockApi({ "/api/templates": templates });
    renderPage();
    await screen.findByLabelText("Your name");
    type("Your name", "Test Owner");
    type("Email", "owner@example.com");
    type("Password", "long enough");
    nextStep();
    fireEvent.click(await screen.findByRole("radio", { name: /Distributor/ }));
    expect(screen.getByLabelText("Distributor name")).toBeTruthy();
    type("Distributor name", "Example Traders");
    type("Address", "1 Market Road");
    type("Your WhatsApp number", "90000 00002");
    nextStep();
    expect(screen.getByRole("group", { name: "Orders" })).toBeTruthy();
    expect(screen.queryByRole("group", { name: "Doctors and services" })).toBeNull();
  });

  it("signs up from the last step and shows the success screen", async () => {
    const fetchMock = mockApi({
      "/api/templates": templates,
      "/api/signup": () => json(200, { public_id: "abc123", template: "clinic", agent: "not_configured" }),
    });
    renderPage();
    await screen.findByLabelText("Your name");
    fillValidClinic();
    submit();

    expect(await screen.findByRole("heading", { name: "Example Dental is set up" })).toBeTruthy();
    expect(screen.getByText("Voice agent not switched on yet")).toBeTruthy();

    const [, init] = fetchMock.mock.calls.find(([url]) => url === "/api/signup")!;
    expect(init?.headers).toMatchObject({ "X-Requested-With": "catalyst" });
    const body = JSON.parse(String(init?.body));
    expect(body.user.email).toBe("owner@example.com");
    expect(body.business).toMatchObject({ template: "clinic", owner_whatsapp: "+919000000001", consent: true });
    expect(body.details.doctors).toEqual([{ name: "Doctor A" }]);
  });

  it("jumps back to step 1 for a taken email and offers login", async () => {
    mockApi({
      "/api/templates": templates,
      "/api/signup": () =>
        json(409, {
          detail: "That email already has an account. Log in instead.",
          code: "EMAIL_TAKEN",
          fields: { "user.email": "That email already has an account." },
        }),
    });
    renderPage();
    await screen.findByLabelText("Your name");
    fillValidClinic();
    submit();

    await waitFor(() => expect(stepLabel()).toContain("1/3"));
    const email = screen.getByLabelText("Email");
    expect(email.getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText("That email already has an account.")).toBeTruthy();
    const banner = screen.getAllByRole("alert").find((el) => el.textContent?.includes("Go to login"))!;
    expect(within(banner).getByRole("link", { name: "Go to login" }).getAttribute("href")).toBe("/login");
  });

  it("explains instead of moving on when the business types didn't load", async () => {
    mockApi({ "/api/templates": () => json(500, { detail: "Something went wrong.", code: "INTERNAL" }) });
    renderPage();
    await screen.findByLabelText("Your name");
    type("Your name", "Test Owner");
    type("Email", "owner@example.com");
    type("Password", "long enough");
    nextStep();
    expect(await screen.findByText("The form didn't load")).toBeTruthy();
    const retry = screen.getByRole("button", { name: /Try again/ });
    const next = screen.getByRole("button", { name: /^Next/ }) as HTMLButtonElement;
    expect(next.disabled).toBe(false); // never silently disabled
    nextStep();
    expect(await screen.findByText(/didn't finish loading/)).toBeTruthy();
    expect(document.activeElement).toBe(retry);
    expect(stepLabel()).toContain("2/3");
  });

  it("says when you're already logged in, and lets you log out to set up another", async () => {
    const fetchMock = mockApi({
      "/api/templates": templates,
      "/api/me": () => json(200, ME),
      "/api/logout": () => json(200, { ok: true }),
    });
    renderPage();
    expect(await screen.findByText("owner@example.com")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Go to your home page" }).getAttribute("href")).toBe("/home");
    fireEvent.click(screen.getByRole("button", { name: "Log out to set up another" }));
    await waitFor(() => expect(screen.queryByText("owner@example.com")).toBeNull());
    expect(fetchMock.mock.calls.some(([url, init]) => url === "/api/logout" && init?.method === "POST")).toBe(true);
  });

  it("sends you home, not to login, when the taken email is the one you're logged in with", async () => {
    mockApi({
      "/api/templates": templates,
      "/api/me": () => json(200, ME),
      "/api/signup": () =>
        json(409, {
          detail: "That email already has an account. Log in instead.",
          code: "EMAIL_TAKEN",
          fields: { "user.email": "That email already has an account." },
        }),
    });
    renderPage();
    await screen.findByLabelText("Your name");
    fillValidClinic();
    submit();
    const banner = await waitFor(() =>
      screen.getAllByRole("alert").find((el) => el.textContent?.includes("logged in with"))!,
    );
    expect(within(banner).getByRole("link", { name: "Go to your home page" }).getAttribute("href")).toBe("/home");
    expect(within(banner).queryByRole("link", { name: "Go to login" })).toBeNull();
  });
});
