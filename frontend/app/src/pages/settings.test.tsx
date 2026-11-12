import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { BookingsSettings, OrdersSettings } from "@/features/settings/api";

import { SettingsPage } from "./settings";

// Fictional only (CLAUDE.md rule 6).
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const CLINIC: BookingsSettings = {
  name: "Example Dental",
  city: "Example City",
  address: "1 Test Road",
  landmark: "",
  sessions: [["10:00", "14:00"]],
  closed_weekdays: [6],
  faqs: [{ q: "Parking?", a: "Yes, in front." }],
  whatsapp_numbers: ["+919000000001"],
  voice: "female",
  slot_min: 15,
  doctors: [
    { id: "doctor-a", name: "Doctor A" },
    { id: "doctor-b", name: "Doctor B" },
  ],
  services: [{ name: "Consultation", fee: "₹300" }],
  red_flags: ["bleeding"],
  emergency_instruction: "Go to the nearest hospital emergency or call 108.",
};

const SHOP: OrdersSettings = {
  name: "Example Traders",
  city: "",
  address: "2 Market Road",
  landmark: "",
  sessions: [["09:30", "19:30"]],
  closed_weekdays: [6],
  faqs: [],
  whatsapp_numbers: [],
  voice: "male",
  min_order: "₹2,000",
  delivery_area: "Within the city",
};

type Handler = (init?: RequestInit) => Response;

function mockApi(settings: BookingsSettings | OrdersSettings, put?: Handler) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    if (String(input) !== "/api/settings") throw new Error(`unexpected fetch ${String(input)}`);
    if (init?.method === "PUT") {
      return put ? put(init) : json(200, { saved: true, agent: "Your front desk is updated.", settings: JSON.parse(String(init.body)) });
    }
    return json(200, { settings, blocks: [], agentConfigured: true });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/settings"]}>
      <Routes>
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/login" element={<p>Login page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

const putBody = (fetchMock: ReturnType<typeof mockApi>) => {
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
  return call ? JSON.parse(String(call[1]!.body)) : undefined;
};

afterEach(() => vi.unstubAllGlobals());

describe("<SettingsPage>", () => {
  it("loads the clinic's settings into the sections", async () => {
    mockApi(CLINIC);
    renderPage();
    expect(((await screen.findByLabelText("Business name")) as HTMLInputElement).value).toBe("Example Dental");
    expect((screen.getByLabelText("Doctor 2") as HTMLInputElement).value).toBe("Doctor B");
    expect((screen.getByLabelText("Service 1 fee") as HTMLInputElement).value).toBe("₹300");
    expect((screen.getByLabelText("WhatsApp number 1") as HTMLInputElement).value).toBe("90000 00001");
    expect(screen.getByRole("link", { name: "Emergencies" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Save changes/ })).toBeNull(); // nothing changed yet
  });

  it("shows the Save bar once something changes, and Discard puts it back", async () => {
    mockApi(CLINIC);
    renderPage();
    const name = (await screen.findByLabelText("Business name")) as HTMLInputElement;
    fireEvent.change(name, { target: { value: "Example Dental Care" } });
    expect(screen.getByText("Unsaved changes")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(name.value).toBe("Example Dental");
    expect(screen.queryByText("Unsaved changes")).toBeNull();
  });

  it("saves the whole template shape, keeping doctor ids", async () => {
    const fetchMock = mockApi(CLINIC);
    renderPage();
    fireEvent.change(await screen.findByLabelText("Doctor 1"), { target: { value: "Doctor A Kumar" } });
    fireEvent.click(screen.getByRole("button", { name: "Remove doctor 2" }));
    fireEvent.click(screen.getByRole("button", { name: /Save changes/ }));

    await waitFor(() => expect(screen.queryByText("Unsaved changes")).toBeNull());
    const body = putBody(fetchMock);
    expect(body.doctors).toEqual([{ id: "doctor-a", name: "Doctor A Kumar" }]);
    expect(body).toMatchObject({ slot_min: 15, sessions: [["10:00", "14:00"]], whatsapp_numbers: ["90000 00001"], red_flags: ["bleeding"] });
  });

  it("drops empty rows instead of blocking the save", async () => {
    const fetchMock = mockApi(CLINIC);
    renderPage();
    await screen.findByLabelText("Business name");
    fireEvent.click(screen.getByRole("button", { name: /Add a question/ }));
    fireEvent.click(screen.getByRole("button", { name: /Add a number/ }));
    fireEvent.change(screen.getByLabelText("Landmark", { exact: false }), { target: { value: "Near the park" } });
    fireEvent.click(screen.getByRole("button", { name: /Save changes/ }));
    await waitFor(() => expect(putBody(fetchMock)).toBeTruthy());
    expect(putBody(fetchMock).faqs).toEqual([{ q: "Parking?", a: "Yes, in front." }]);
    expect(putBody(fetchMock).whatsapp_numbers).toEqual(["90000 00001"]);
  });

  it("marks fields before sending when something required is missing", async () => {
    const fetchMock = mockApi(CLINIC);
    renderPage();
    fireEvent.change(await screen.findByLabelText("Address"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /Save changes/ }));
    expect(await screen.findByText("Please fix the highlighted fields.")).toBeTruthy();
    expect(screen.getByLabelText("Address").getAttribute("aria-invalid")).toBe("true");
    expect(putBody(fetchMock)).toBeUndefined();
  });

  it("shows the backend's message on the right field and keeps what was typed", async () => {
    mockApi(CLINIC, () =>
      json(409, {
        detail: "One of these WhatsApp numbers already belongs to another business.",
        code: "WHATSAPP_TAKEN",
        fields: { whatsapp_numbers: "One of these WhatsApp numbers already belongs to another business." },
      }),
    );
    renderPage();
    const number = (await screen.findByLabelText("WhatsApp number 1")) as HTMLInputElement;
    fireEvent.change(number, { target: { value: "90000 00009" } });
    fireEvent.click(screen.getByRole("button", { name: /Save changes/ }));
    const alerts = await screen.findAllByText("One of these WhatsApp numbers already belongs to another business.");
    expect(alerts.length).toBeGreaterThanOrEqual(2); // the banner and the field
    expect(number.value).toBe("90000 00009");
    expect(screen.getByText("Unsaved changes")).toBeTruthy();
  });

  it("explains a doctor who can't be removed yet", async () => {
    mockApi(CLINIC, () =>
      json(422, { detail: "Doctor B has 2 upcoming booking(s). Move or cancel them before removing the doctor.", code: "VALIDATION" }),
    );
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Remove doctor 2" }));
    fireEvent.click(screen.getByRole("button", { name: /Save changes/ }));
    expect(await screen.findByText(/Doctor B has 2 upcoming booking/)).toBeTruthy();
  });

  it("shows the wholesale terms instead of doctors for a distributor", async () => {
    const fetchMock = mockApi(SHOP);
    renderPage();
    expect(((await screen.findByLabelText("Minimum order", { exact: false })) as HTMLInputElement).value).toBe("₹2,000");
    expect(screen.queryByLabelText("Doctor 1")).toBeNull();
    expect(screen.queryByRole("link", { name: "Emergencies" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Delivery area", { exact: false }), { target: { value: "Whole district" } });
    fireEvent.click(screen.getByRole("button", { name: /Save changes/ }));
    await waitFor(() => expect(putBody(fetchMock)).toBeTruthy());
    const body = putBody(fetchMock);
    expect(body).toMatchObject({ delivery_area: "Whole district", min_order: "₹2,000", voice: "male" });
    expect(body).not.toHaveProperty("doctors");
  });

  it("sends a logged-out owner to login", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async () => json(401, { detail: "Please log in to continue.", code: "UNAUTHENTICATED" })),
    );
    renderPage();
    expect(await screen.findByText("Login page")).toBeTruthy();
  });

  it("toggles a closed day", async () => {
    const fetchMock = mockApi(CLINIC);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Closed on Monday" }));
    fireEvent.click(screen.getByRole("button", { name: /Save changes/ }));
    await waitFor(() => expect(putBody(fetchMock)).toBeTruthy());
    expect(putBody(fetchMock).closed_weekdays).toEqual([0, 6]);
    expect(within(document.body).getByRole("button", { name: "Closed on Sunday" }).getAttribute("aria-pressed")).toBe("true");
  });
});
