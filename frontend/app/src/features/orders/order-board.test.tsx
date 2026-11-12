import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DeskPage } from "@/pages/desk";

import type { Order, Product } from "./api";

// Fictional only (CLAUDE.md rule 6).
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const ME = {
  user: { name: "Test Owner", email: "owner@example.com" },
  business: { name: "Example Traders", template: "wholesale", public_id: "abc123", labels: { booking: "Order" } },
};

const PRODUCTS: Product[] = [
  { id: 1, name: "ORS powder orange", pack_size: "21 g sachet", rate_paise: 2200, rate: "₹22", in_stock: true, active: true },
  { id: 2, name: "Cotton roll", pack_size: "100 g", rate_paise: 5800, rate: "₹58", in_stock: false, active: true },
];

const order = (over: Partial<Order>): Order => ({
  id: 1,
  number: 14,
  shop_name: "Example Stores",
  contact_name: "Test Contact",
  phone: "+919000000005",
  notes: null,
  status: "new",
  next: ["confirmed", "cancelled"],
  source: "whatsapp",
  items: [{ product_id: 1, name: "ORS powder orange", pack_size: "21 g sachet", qty: 10, rate_paise: 2200, rate: "₹22", amount: "₹220" }],
  total_paise: 22000,
  total: "₹220",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...over,
});

const ORDERS = [
  order({}),
  order({ id: 2, number: 13, shop_name: "Second Shop", status: "delivered", next: [], source: "phone" }),
];

type Handler = (init?: RequestInit) => Response;

function mockApi(overrides: Record<string, Handler> = {}) {
  const routes: Record<string, Handler> = {
    "/api/me": () => json(200, ME),
    "/api/desk/day": () => json(404, { detail: "This business doesn't keep a schedule.", code: "NOT_FOUND" }),
    "/api/orders": () => json(200, { orders: ORDERS, next_before_id: null }),
    "/api/catalog": () => json(200, { products: PRODUCTS }),
    "/api/inbox": () => json(200, []),
    "/api/calls": () => json(200, []),
    "/api/stats": () => json(200, { sentence: "", urgent_open: 0, callbacks_open: 0, appointments: 0, calls: 0 }),
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
      </Routes>
    </MemoryRouter>,
  );
}

const posts = (fetchMock: ReturnType<typeof mockApi>, url: string) =>
  fetchMock.mock.calls.filter(([u, init]) => u === url && init?.method === "POST").map(([, init]) => JSON.parse(String(init!.body)));

async function openNewOrder() {
  fireEvent.click(await screen.findByRole("button", { name: /New order/ }));
  return screen.findByRole("dialog", { name: "New order" });
}

function fillOrder(dialog: HTMLElement) {
  fireEvent.change(within(dialog).getByLabelText("Shop name"), { target: { value: "Example Stores" } });
  fireEvent.change(within(dialog).getByLabelText("Product 1"), { target: { value: "ors" } });
  fireEvent.click(within(dialog).getByRole("button", { name: /ORS powder orange/ }));
  fireEvent.change(within(dialog).getByLabelText("Qty for product 1"), { target: { value: "10" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("order board (wholesale desk)", () => {
  it("shows open orders by default, with today's counts", async () => {
    mockApi();
    renderDesk();
    expect(await screen.findByRole("heading", { name: "Example Traders" })).toBeTruthy();
    const list = screen.getByRole("list", { name: "Orders" });
    expect(within(list).getByText("Example Stores")).toBeTruthy();
    expect(within(list).queryByText("Second Shop")).toBeNull(); // delivered: under "Done"

    fireEvent.click(screen.getByRole("button", { name: /^Done/ }));
    expect(within(screen.getByRole("list", { name: "Orders" })).getByText("Second Shop")).toBeTruthy();
  });

  it("moves an order to its next status with one button", async () => {
    const fetchMock = mockApi({ "/api/orders/1/status": () => json(200, order({ status: "confirmed" })) });
    renderDesk();
    fireEvent.click(await screen.findByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(posts(fetchMock, "/api/orders/1/status")).toEqual([{ status: "confirmed" }]));
  });

  it("cancels only from the menu, after asking", async () => {
    const fetchMock = mockApi({ "/api/orders/1/status": () => json(200, order({ status: "cancelled" })) });
    renderDesk();
    const more = await screen.findByRole("button", { name: "More for order 14" });
    fireEvent.pointerDown(more, { button: 0, ctrlKey: false, pointerType: "mouse" });
    fireEvent.click(await screen.findByRole("menuitem", { name: "Cancel order" }));
    const dialog = await screen.findByRole("dialog", { name: "Cancel this order?" });
    expect(posts(fetchMock, "/api/orders/1/status")).toHaveLength(0);
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel order" }));
    await waitFor(() => expect(posts(fetchMock, "/api/orders/1/status")).toEqual([{ status: "cancelled" }]));
  });

  it("adds an order from the sheet, with a running total", async () => {
    const fetchMock = mockApi({ "/api/orders": (init) => (init?.method === "POST" ? json(200, order({ id: 3, number: 15 })) : json(200, { orders: ORDERS, next_before_id: null })) });
    renderDesk();
    const dialog = await openNewOrder();
    fillOrder(dialog);
    expect(within(dialog).getAllByText("₹220").length).toBeGreaterThan(0);
    fireEvent.click(within(dialog).getByRole("button", { name: /Save order/ }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const [body] = posts(fetchMock, "/api/orders");
    expect(body).toMatchObject({ shop_name: "Example Stores", items: [{ product_id: 1, qty: 10 }], source: "walk_in", allow_duplicate: false });
    expect(typeof body.idempotency_key).toBe("string");
  });

  it("won't pick an out-of-stock product", async () => {
    mockApi();
    renderDesk();
    const dialog = await openNewOrder();
    fireEvent.change(within(dialog).getByLabelText("Product 1"), { target: { value: "cotton" } });
    const option = within(dialog).getByRole("button", { name: /Cotton roll/ }) as HTMLButtonElement;
    expect(option.disabled).toBe(true);
    expect(within(option).getByText("Out of stock")).toBeTruthy();
  });

  it("keeps the draft when the sheet is closed", async () => {
    mockApi();
    renderDesk();
    const dialog = await openNewOrder();
    fillOrder(dialog);
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: /Continue order · ₹220/ }));
    const again = await screen.findByRole("dialog", { name: "New order" });
    expect((within(again).getByLabelText("Shop name") as HTMLInputElement).value).toBe("Example Stores");
  });

  it("points to the open duplicate and can still save a new one with the same key", async () => {
    let n = 0;
    const fetchMock = mockApi({
      "/api/orders": (init) => {
        if (init?.method !== "POST") return json(200, { orders: ORDERS, next_before_id: null });
        return ++n === 1
          ? json(409, { detail: "That order is already open.", code: "DUPLICATE_ORDER", alternatives: [order({})] })
          : json(200, order({ id: 4, number: 16 }));
      },
    });
    renderDesk();
    const dialog = await openNewOrder();
    fillOrder(dialog);
    fireEvent.click(within(dialog).getByRole("button", { name: /Save order/ }));
    expect(await within(dialog).findByText(/Order #14 for Example Stores with the same items is still open/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Save as a new order" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const [first, second] = posts(fetchMock, "/api/orders");
    expect(second.allow_duplicate).toBe(true);
    expect(second.idempotency_key).toBe(first.idempotency_key);
  });

  it("saves again by itself once when two orders took the same number", async () => {
    let n = 0;
    const fetchMock = mockApi({
      "/api/orders": (init) => {
        if (init?.method !== "POST") return json(200, { orders: ORDERS, next_before_id: null });
        return ++n === 1 ? json(409, { detail: "Please save again.", code: "TRY_AGAIN" }) : json(200, order({ id: 5, number: 17 }));
      },
    });
    renderDesk();
    const dialog = await openNewOrder();
    fillOrder(dialog);
    fireEvent.click(within(dialog).getByRole("button", { name: /Save order/ }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(posts(fetchMock, "/api/orders")).toHaveLength(2);
  });

  it("asks for the shop and a product before sending", async () => {
    const fetchMock = mockApi();
    renderDesk();
    const dialog = await openNewOrder();
    fireEvent.click(within(dialog).getByRole("button", { name: /Save order/ }));
    expect(await within(dialog).findByText("Please write the shop's name.")).toBeTruthy();
    expect(within(dialog).getByText("Add at least one product.")).toBeTruthy();
    expect(posts(fetchMock, "/api/orders")).toHaveLength(0);
  });
});
