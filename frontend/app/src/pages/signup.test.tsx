import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CLINIC, WHOLESALE } from "@/test/fixtures";

import { SignupPage } from "./signup";

type Route = (init?: RequestInit) => Response;

function mockApi(routes: Record<string, Route>) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input);
    const handler = routes[url];
    if (!handler) throw new Error(`unexpected fetch ${url}`);
    return handler(init);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const templates = () => json(200, { templates: [CLINIC, WHOLESALE] });

function renderPage(path = "/signup") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <SignupPage />
    </MemoryRouter>,
  );
}

const type = (label: string | RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

function fillValidClinic() {
  type("Your name", "Test Owner");
  type("Email", "owner@example.com");
  type("Password", "long enough");
  type("Clinic name", "Example Dental");
  type("Address", "1 Test Road");
  type("Your WhatsApp number", "90000 00001");
  type("Doctor 1 name", "Doctor A");
  fireEvent.click(screen.getByRole("checkbox"));
}

const submit = () => fireEvent.click(screen.getByRole("button", { name: "Create my front desk" }));

afterEach(() => vi.unstubAllGlobals());

describe("<SignupPage>", () => {
  it("prefills the first template and shows its section", async () => {
    mockApi({ "/api/templates": templates });
    renderPage();
    expect(await screen.findByRole("radio", { name: /Clinic/ })).toHaveProperty("ariaChecked", "true");
    expect(screen.getByRole("group", { name: "Doctors and services" })).toBeTruthy();
    expect((screen.getByLabelText("Service 1") as HTMLInputElement).value).toBe("Consultation");
  });

  it("switches to the orders section when the owner picks the other template", async () => {
    mockApi({ "/api/templates": templates });
    renderPage();
    fireEvent.click(await screen.findByRole("radio", { name: /Distributor/ }));
    expect(screen.getByRole("group", { name: "Orders" })).toBeTruthy();
    expect(screen.queryByRole("group", { name: "Doctors and services" })).toBeNull();
    expect(screen.getByLabelText("Distributor name")).toBeTruthy();
  });

  it("checks the form in the browser before sending anything", async () => {
    const fetchMock = mockApi({ "/api/templates": templates });
    renderPage();
    await screen.findByRole("radio", { name: /Clinic/ });
    submit();
    expect(await screen.findByText("Please fix the highlighted fields.")).toBeTruthy();
    expect(screen.getByLabelText("Email").getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText("Enter an email like name@example.com.")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1); // only the templates load
  });

  it("signs up and shows the success screen", async () => {
    const fetchMock = mockApi({
      "/api/templates": templates,
      "/api/signup": () => json(200, { public_id: "abc123", template: "clinic", agent: "not_configured" }),
    });
    renderPage();
    await screen.findByRole("radio", { name: /Clinic/ });
    fillValidClinic();
    submit();

    expect(await screen.findByRole("heading", { name: "Example Dental is set up" })).toBeTruthy();
    expect(screen.getByText("Voice agent not switched on yet")).toBeTruthy();

    const [, init] = fetchMock.mock.calls.find(([url]) => url === "/api/signup")!;
    expect(init?.headers).toMatchObject({ "X-Requested-With": "catalyst" });
    const body = JSON.parse(String(init?.body));
    expect(body.business).toMatchObject({ template: "clinic", owner_whatsapp: "+919000000001", consent: true });
    expect(body.details.doctors).toEqual([{ name: "Doctor A" }]);
  });

  it("puts server errors on the right inputs and offers login for a taken email", async () => {
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
    await screen.findByRole("radio", { name: /Clinic/ });
    fillValidClinic();
    submit();

    const email = screen.getByLabelText("Email");
    await waitFor(() => expect(email.getAttribute("aria-invalid")).toBe("true"));
    expect(screen.getByText("That email already has an account.")).toBeTruthy();
    const banner = screen.getAllByRole("alert").find((el) => el.textContent?.includes("Go to login"))!;
    expect(within(banner).getByRole("link", { name: "Go to login" }).getAttribute("href")).toBe("/login");
  });

  it("offers a retry when the templates don't load", async () => {
    mockApi({ "/api/templates": () => json(500, { detail: "Something went wrong.", code: "INTERNAL" }) });
    renderPage();
    expect(await screen.findByText("The form didn't load")).toBeTruthy();
    const retry = screen.getByRole("button", { name: /Try again/ });
    // The submit button stays usable and explains what's wrong instead of silently doing nothing.
    const create = screen.getByRole("button", { name: "Create my front desk" }) as HTMLButtonElement;
    expect(create.disabled).toBe(false);
    submit();
    expect(await screen.findByText(/didn't finish loading/)).toBeTruthy();
    expect(document.activeElement).toBe(retry);
  });

  it("clears the 'still loading' message once the form has loaded", async () => {
    let release: () => void = () => {};
    const slow = new Promise<void>((r) => (release = r));
    // The templates answer only when the test says so.
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input) => {
        if (String(input) === "/api/templates") {
          await slow;
          return templates();
        }
        throw new Error(`unexpected fetch ${String(input)}`);
      }),
    );
    renderPage();
    submit();
    expect(await screen.findByText(/still loading/)).toBeTruthy();
    release();
    await screen.findByRole("radio", { name: /Clinic/ });
    expect(screen.queryByText(/still loading/)).toBeNull();
  });
});
