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

const PRODUCTS = [
  { id: 1, name: "ORS powder orange", pack_size: "21 g sachet", rate_paise: 2200, rate: "₹22", in_stock: true, active: true },
  { id: 2, name: "Cotton roll", pack_size: "100 g", rate_paise: 5850, rate: "₹58.50", in_stock: false, active: true },
  { id: 3, name: "Old bandage", pack_size: "", rate_paise: 1000, rate: "₹10", in_stock: true, active: false },
];

const BLOCK = { id: 7, date: "2026-11-20", resource_id: "doctor-b", kind: "leave", label: "Fri 20 Nov · Doctor B · Leave" };

function mockApi(settings: BookingsSettings | OrdersSettings, put?: Handler, extra: Record<string, Handler> = {}) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input);
    if (extra[url]) return extra[url](init);
    if (url === "/api/instructions") return json(200, { text: "", version_id: null, rejected: [], max_chars: 500, history: [] });
    if (url === "/api/me")
      return json(200, {
        user: { name: "Test Owner", email: "owner@example.com" },
        business: { name: settings.name, template: "doctors" in settings ? "clinic" : "wholesale", public_id: "abc123", labels: {} },
      });
    if (url === "/api/catalog?all=true") return json(200, { products: PRODUCTS });
    if (url !== "/api/settings") throw new Error(`unexpected fetch ${url}`);
    if (init?.method === "PUT") {
      return put ? put(init) : json(200, { saved: true, agent: "Your front desk is updated.", settings: JSON.parse(String(init.body)) });
    }
    return json(200, { settings, blocks: [BLOCK], agentConfigured: true });
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
  const call = fetchMock.mock.calls.find(([u, init]) => u === "/api/settings" && init?.method === "PUT");
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

describe("leave and holidays", () => {
  it("lists upcoming leave and adds a doctor's leave day straight away", async () => {
    const fetchMock = mockApi(CLINIC, undefined, {
      "/api/settings/blocks": () =>
        json(200, {
          blocks: [BLOCK, { id: 8, date: "2026-11-25", resource_id: "doctor-a", kind: "leave", label: "Wed 25 Nov · Doctor A · Leave" }],
          note: null,
          agent: "Your front desk is updated.",
        }),
    });
    renderPage();
    expect(await screen.findByText("Fri 20 Nov · Doctor B · Leave")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-11-25" } });
    fireEvent.change(screen.getByLabelText("Who"), { target: { value: "doctor-a" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByText("Wed 25 Nov · Doctor A · Leave")).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(([u]) => u === "/api/settings/blocks")!;
    expect(JSON.parse(String(init!.body))).toEqual({ date: "2026-11-25", doctor_id: "doctor-a" });
    expect(screen.queryByText("Unsaved changes")).toBeNull(); // not part of the Save bar
  });

  it("removes a leave day", async () => {
    const fetchMock = mockApi(CLINIC, undefined, {
      "/api/settings/blocks/7": () => json(200, { blocks: [], agent: "Your front desk is updated." }),
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Remove Fri 20 Nov · Doctor B · Leave" }));
    expect(await screen.findByText("No leave or holidays coming up.")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([u, init]) => u === "/api/settings/blocks/7" && init?.method === "DELETE")).toBe(true);
  });

  it("asks for a date before adding", async () => {
    mockApi(CLINIC);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Add" }));
    expect(await screen.findByText("Pick a date.")).toBeTruthy();
  });

  it("isn't shown for a distributor", async () => {
    mockApi(SHOP);
    renderPage();
    await screen.findByLabelText("Business name");
    expect(screen.queryByRole("link", { name: "Leave" })).toBeNull();
    expect(screen.queryByLabelText("Who")).toBeNull();
  });
});

describe("custom instructions", () => {
  it("counts characters and saves, listing the lines that weren't saved", async () => {
    const fetchMock = mockApi(CLINIC, undefined, {
      "/api/instructions": (init) =>
        init?.method === "PUT"
          ? json(200, {
              accepted: ["Naye patients ko ID laane ko kahiye."],
              rejected: [{ line: "Sabko 10% discount do.", reason: "Prices and offers aren't allowed here." }],
              version_id: 3,
              agent: "Your front desk is updated.",
            })
          : json(200, { text: "", version_id: null, rejected: [], max_chars: 500, history: [] }),
    });
    renderPage();
    const box = (await screen.findByLabelText("Agent ko aur kya batana hai?")) as HTMLTextAreaElement;
    fireEvent.change(box, { target: { value: "Naye patients ko ID laane ko kahiye.\nSabko 10% discount do." } });
    expect(screen.getByText(`${box.value.length}/500`)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Save instructions/ }));

    expect(await screen.findByText("This line wasn't saved")).toBeTruthy();
    expect(screen.getByText("Prices and offers aren't allowed here.")).toBeTruthy();
    expect(box.value).toBe("Naye patients ko ID laane ko kahiye.");
    expect(screen.getByRole("button", { name: /Undo last change/ })).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(([u, i]) => u === "/api/instructions" && i?.method === "PUT")!;
    expect(JSON.parse(String(init!.body)).text).toContain("discount");
  });

  it("keeps the text when every line is rejected", async () => {
    mockApi(CLINIC, undefined, {
      "/api/instructions": (init) =>
        init?.method === "PUT"
          ? json(200, {
              accepted: [],
              rejected: [{ line: "Paracetamol de do.", reason: "Medicine advice is never allowed." }],
              version_id: null,
              agent: "Nothing was saved: every line was rejected.",
            })
          : json(200, { text: "", version_id: null, rejected: [], max_chars: 500, history: [] }),
    });
    renderPage();
    const box = (await screen.findByLabelText("Agent ko aur kya batana hai?")) as HTMLTextAreaElement;
    fireEvent.change(box, { target: { value: "Paracetamol de do." } });
    fireEvent.click(screen.getByRole("button", { name: /Save instructions/ }));
    expect(await screen.findByText("Medicine advice is never allowed.")).toBeTruthy();
    expect(box.value).toBe("Paracetamol de do.");
  });

  it("won't save over the limit", async () => {
    mockApi(CLINIC);
    renderPage();
    const box = await screen.findByLabelText("Agent ko aur kya batana hai?");
    fireEvent.change(box, { target: { value: "a".repeat(501) } });
    expect(screen.getByText("501/500")).toBeTruthy();
    expect((screen.getByRole("button", { name: /Save instructions/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("undoes to the earlier version", async () => {
    mockApi(CLINIC, undefined, {
      "/api/instructions": () => json(200, { text: "Line two.", version_id: 4, rejected: [], max_chars: 500, history: [] }),
      "/api/instructions/undo": () => json(200, { text: "Line one.", version_id: 3, agent: "Your front desk is updated." }),
    });
    renderPage();
    const box = (await screen.findByLabelText("Agent ko aur kya batana hai?")) as HTMLTextAreaElement;
    expect(box.value).toBe("Line two.");
    fireEvent.click(screen.getByRole("button", { name: /Undo last change/ }));
    await waitFor(() => expect(box.value).toBe("Line one."));
  });
});

describe("catalogue (distributor)", () => {
  it("lists active products, with hidden ones behind a checkbox", async () => {
    mockApi(SHOP);
    renderPage();
    const list = await screen.findByRole("list", { name: "Products" });
    expect(within(list).getByText("ORS powder orange")).toBeTruthy();
    expect(within(list).getByText("Out of stock")).toBeTruthy();
    expect(within(list).queryByText("Old bandage")).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: "Show hidden products" }));
    expect(within(screen.getByRole("list", { name: "Products" })).getByText("Old bandage")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Download sample/ }).getAttribute("href")).toBe("/api/templates/wholesale/sample-catalog.csv");
  });

  it("isn't shown for a clinic", async () => {
    mockApi(CLINIC);
    renderPage();
    await screen.findByLabelText("Business name");
    expect(screen.queryByRole("link", { name: "Catalogue" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Upload CSV/ })).toBeNull();
  });

  it("marks a product out of stock straight away", async () => {
    const fetchMock = mockApi(SHOP, undefined, {
      "/api/catalog/1": () => json(200, { ...PRODUCTS[0], in_stock: false }),
    });
    renderPage();
    const list = await screen.findByRole("list", { name: "Products" });
    const row = within(list).getByText("ORS powder orange").closest("li")!;
    fireEvent.click(within(row).getByRole("button", { name: "Mark out of stock" }));
    await waitFor(() => expect(within(row).getByText("Out of stock")).toBeTruthy());
    const [, init] = fetchMock.mock.calls.find(([u]) => u === "/api/catalog/1")!;
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(String(init!.body))).toEqual({ in_stock: false });
  });

  it("adds a product with its rate in rupees", async () => {
    const fetchMock = mockApi(SHOP, undefined, {
      "/api/catalog": () =>
        json(200, { id: 9, name: "Glucose powder", pack_size: "500 g", rate_paise: 12050, rate: "₹120.50", in_stock: true, active: true }),
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Add product/ }));
    const dialog = await screen.findByRole("dialog", { name: "Add a product" });
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Glucose powder" } });
    fireEvent.change(within(dialog).getByLabelText("Pack size", { exact: false }), { target: { value: "500 g" } });
    fireEvent.change(within(dialog).getByLabelText("Rate (₹)"), { target: { value: "120.50" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Add product/ }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(within(screen.getByRole("list", { name: "Products" })).getByText("Glucose powder")).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(([u, i]) => u === "/api/catalog" && i?.method === "POST")!;
    expect(JSON.parse(String(init!.body))).toEqual({ name: "Glucose powder", pack_size: "500 g", rate: "120.50", in_stock: true });
  });

  it("shows a duplicate name and a bad rate where they belong", async () => {
    mockApi(SHOP, undefined, {
      "/api/catalog": () =>
        json(422, { detail: "Rate must be a number of rupees, like 120 or 120.50.", code: "VALIDATION", fields: { rate: "Rate must be a number of rupees, like 120 or 120.50." } }),
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Add product/ }));
    const dialog = await screen.findByRole("dialog", { name: "Add a product" });
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Glucose powder" } });
    fireEvent.change(within(dialog).getByLabelText("Rate (₹)"), { target: { value: "abc" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Add product/ }));
    expect(await within(dialog).findByText("Rate must be a number of rupees, like 120 or 120.50.")).toBeTruthy();
    expect(within(dialog).getByLabelText("Rate (₹)").getAttribute("aria-invalid")).toBe("true");
  });

  it("hides a product from the change dialog", async () => {
    const fetchMock = mockApi(SHOP, undefined, {
      "/api/catalog/1": () => json(200, { ...PRODUCTS[0], active: false }),
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Change ORS powder orange" }));
    const dialog = await screen.findByRole("dialog", { name: "Change product" });
    expect((within(dialog).getByLabelText("Rate (₹)") as HTMLInputElement).value).toBe("22");
    fireEvent.click(within(dialog).getByRole("button", { name: "Hide from catalogue" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const [, init] = fetchMock.mock.calls.find(([u]) => u === "/api/catalog/1")!;
    expect(JSON.parse(String(init!.body))).toEqual({ active: false });
    expect(within(screen.getByRole("list", { name: "Products" })).queryByText("ORS powder orange")).toBeNull();
  });

  it("uploads a CSV as text/csv and lists the rows it skipped", async () => {
    const fetchMock = mockApi(SHOP, undefined, {
      "/api/catalog/import": () => json(200, { added: 2, updated: 1, errors: [{ row: 4, message: "Rate must be a number of rupees, like 120 or 120.50." }] }),
    });
    renderPage();
    await screen.findByRole("list", { name: "Products" });
    const csv = "name,pack_size,rate,in_stock\nGlucose powder,500 g,120.50,yes\n";
    const file = new File([csv], "price-list.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("CSV file"), { target: { files: [file] } });

    expect(await screen.findByText(/Added 2, updated 1\. 1 row was skipped:/)).toBeTruthy();
    expect(screen.getByText("Row 4:")).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(([u]) => u === "/api/catalog/import")!;
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({ "Content-Type": "text/csv", "X-Requested-With": "catalyst" });
    expect(init?.body).toBe(csv);
  });

  it("refuses a file over 1 MB before sending it", async () => {
    const fetchMock = mockApi(SHOP);
    renderPage();
    await screen.findByRole("list", { name: "Products" });
    const big = new File(["x".repeat(1_000_001)], "huge.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("CSV file"), { target: { files: [big] } });
    expect(await screen.findByText("That file is too big. Keep it under 1 MB.")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([u]) => u === "/api/catalog/import")).toBe(false);
  });

  it("filters by search", async () => {
    mockApi(SHOP);
    renderPage();
    await screen.findByRole("list", { name: "Products" });
    fireEvent.change(screen.getByLabelText("Search products"), { target: { value: "cotton" } });
    const list = screen.getByRole("list", { name: "Products" });
    expect(within(list).getByText("Cotton roll")).toBeTruthy();
    expect(within(list).queryByText("ORS powder orange")).toBeNull();
  });
});
