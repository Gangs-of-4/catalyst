/** Order board and catalogue endpoints (contracts.md §6.1, orders template). */
import { api } from "@/lib/api";

export type OrderStatus = "new" | "confirmed" | "dispatched" | "delivered" | "cancelled";
export type OrderSource = "phone" | "whatsapp" | "walk_in";

export type OrderItem = {
  product_id: number;
  name: string;
  pack_size: string;
  qty: number;
  rate_paise: number;
  rate: string;
  amount: string;
};

export type Order = {
  id: number;
  number: number;
  shop_name: string;
  contact_name: string | null;
  phone: string | null;
  notes: string | null;
  status: OrderStatus;
  /** The statuses it may move to (the backend's lifecycle table). */
  next: OrderStatus[];
  source: OrderSource;
  items: OrderItem[];
  total_paise: number;
  total: string;
  created_at: string;
  updated_at: string;
};

export type Product = {
  id: number;
  name: string;
  pack_size: string;
  rate_paise: number;
  rate: string;
  in_stock: boolean;
  active: boolean;
};

export type OrderPage = { orders: Order[]; next_before_id: number | null };

export type NewOrder = {
  shop_name: string;
  contact_name: string;
  phone: string;
  notes: string;
  items: { product_id: number; qty: number }[];
  source: "walk_in" | "whatsapp";
  idempotency_key: string;
  allow_duplicate: boolean;
};

export const PAGE = 50;

export const getOrders = (beforeId: number | null, signal?: AbortSignal) =>
  api<OrderPage>(`/api/orders?limit=${PAGE}${beforeId ? `&before_id=${beforeId}` : ""}`, { signal });

export const createOrder = (body: NewOrder) => api<Order>("/api/orders", { method: "POST", body });

export const setOrderStatus = (id: number, status: OrderStatus) =>
  api<Order>(`/api/orders/${id}/status`, { method: "POST", body: { status } });

export const getCatalog = (signal?: AbortSignal) => api<{ products: Product[] }>("/api/catalog", { signal });

/** Paise as the backend writes rupees: Indian grouping, paise only when there are any (₹1,23,456 or ₹99.50). */
export function formatInr(paise: number): string {
  const whole = paise % 100 === 0;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(paise / 100);
}

/** Every product, hidden ones too, for the settings page. */
export const getAllProducts = (signal?: AbortSignal) => api<{ products: Product[] }>("/api/catalog?all=true", { signal });

/** `rate` in rupees as typed ("120" or "120.50"); the backend parses and checks it. */
export type ProductIn = { name: string; pack_size: string; rate: string; in_stock: boolean };

export const addProduct = (p: ProductIn) => api<Product>("/api/catalog", { method: "POST", body: p });

export const updateProduct = (id: number, changes: Partial<ProductIn> & { active?: boolean }) =>
  api<Product>(`/api/catalog/${id}`, { method: "PUT", body: changes });

export type ImportResult = { added: number; updated: number; errors: { row: number; message: string }[] };

/**
 * The CSV file as the raw body (`text/csv`, at most 1 MB): good rows are kept, bad ones listed. The
 * bytes go unchanged, so a file saved in another encoding (Excel's ANSI) reaches the backend's
 * "Save the file as CSV (UTF-8)" check instead of being silently garbled in the browser.
 */
export const importCatalog = (file: Blob | string) =>
  api<ImportResult>("/api/catalog/import", { method: "POST", raw: { body: file, contentType: "text/csv" } });
